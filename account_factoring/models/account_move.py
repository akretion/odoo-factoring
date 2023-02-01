# Copyright (C) 2021 - TODAY Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class AccountMove(models.Model):
    _inherit = "account.move"

    # new state capturing the factoring state.
    # we avoid touching the original payment_state to avoid side effects
    payment_state_with_factor = fields.Selection(
        selection=[
            ("not_paid", "Not Paid"),
            ("to_transfer_to_factor", "To Transfer to Factor"),  # added for factoring
            ("submitted_to_factor", "Submitted to Factor"),  # added for factoring
            ("transferred_to_factor", "Transferred to Factor"),  # added for factoring
            ("factor_paid", "Factor Paid"),  # added for factoring
            ("in_payment", "In Payment"),
            ("paid", "Paid"),
            ("partial", "Partially Paid"),
            ("reversed", "Reversed"),
            ("invoicing_legacy", "Invoicing App Legacy"),
        ],
        string="Payment/Factor Status",
        store=True,
        readonly=True,
        copy=False,
        tracking=True,
        help="payment status with factor",
        compute="_compute_payment_state_with_factor",
    )

    factor_transfer_id = fields.Many2one(
        "account.move",
        help="Credit transfer to the Factor",
        copy=False,
    )
    factor_payment_id = fields.Many2one(
        "account.move",
        help="Move with the effect of the payment from the Customer to the Factor",
        copy=False,
    )

    @api.depends(
        "payment_state",
        "payment_mode_id",
        "factor_transfer_id",
        "factor_payment_id",
        "factor_transfer_id.state",
        "factor_payment_id.state",
    )
    def _compute_payment_state_with_factor(self):
        for move in self:
            if (
                move.move_type in ("out_invoice", "out_refund")
                and move.payment_mode_id
                and move.payment_mode_id.fixed_journal_id
                and move.payment_mode_id.fixed_journal_id.is_factor
            ):
                # TODO submitted_to_factor when in_payment ?
                # see _get_invoice_in_payment_state in account and EE
                if (
                    move.payment_state in ("partial", "not_paid")
                    and move.state != "cancel"
                ):
                    if (
                        move.factor_transfer_id
                        and move.factor_transfer_id.state == "draft"
                    ):
                        move.payment_state_with_factor = "submitted_to_factor"
                    else:
                        move.payment_state_with_factor = "to_transfer_to_factor"
                elif move.payment_state == "paid":
                    if (
                        move.factor_payment_id
                        and move.factor_payment_id.state == "posted"
                    ):
                        move.payment_state_with_factor = "factor_paid"
                    else:
                        move.payment_state_with_factor = "transferred_to_factor"
                else:
                    move.payment_state_with_factor = move.payment_state
            else:
                move.payment_state_with_factor = move.payment_state

    def button_draft(self):
        "Will cancel any related factor transfer or related factor payment"
        to_cancel_factor = self.env["account.move"]
        for move in self:
            if (
                move.move_type == "out_invoice"
                and move.payment_mode_id
                and move.payment_mode_id.fixed_journal_id
                and move.payment_mode_id.fixed_journal_id.is_factor
            ):
                to_cancel_factor += move.factor_payment_id
                to_cancel_factor += move.factor_transfer_id
        res = super().button_draft()  # 1st unreconcile to enable cancel
        if to_cancel_factor:  # avoids loop with empty set
            to_cancel_factor.with_context().button_draft()
            to_cancel_factor.with_context().button_cancel()
        return res

    def button_transfer_to_factor(self):
        """
        Unlike the original account.payment.register wizard,
        we don't transfer invoices in batch because we need
        instead a per invoice /per partner fine account.move.line control
        """
        for inv in self:
            wiz = (
                self.env["account.payment.register"]
                .with_context(
                    {
                        "active_model": "account.move",
                        "active_ids": [inv.id],
                    }
                )
                .create({})
            )
            wiz.action_create_payments()
        return True

    def _post(self, soft=True):
        """
        In case the factor transfer is validated manually, we automatically reconcile
        the transfer with its invoice.
        """
        res = super()._post(soft=soft)
        for move in self:
            auto_reconcile = self.search(
                [("factor_transfer_id", "=", move.id)], limit=1
            )
            if auto_reconcile:
                lines = self.env["account.move.line"].search(
                    [
                        ("move_id", "in", [move.id, auto_reconcile.id]),
                        ("account_internal_type", "in", ("receivable", "payable")),
                        ("reconciled", "=", False),
                    ]
                )
                lines.with_context(
                    {
                        # context to avoid errors in account.payment#_synchronize_from_moves
                        "skip_account_move_synchronization": True,
                        "factor_move_synchronization": True,
                    }
                ).reconcile()
        return res

    def button_factor_paid(self):
        """
        Compute the proper holdback amounts to release.
        The holdback proportional to the invoice amount is always fully
        released and reconciled with the transfer holdback. The limit holdback
        is more subtle to release.
        """
        self.ensure_one()
        if self.factor_payment_id and self.factor_payment_id.state != "cancel":
            raise UserError(_("Invoice already has a payment move!"))
        if self.payment_state_with_factor != "transferred_to_factor":
            raise UserError(_("Invoice should be transferred to Factor!"))

        lines = self.factor_transfer_id.line_ids.filtered(
            lambda line: float_compare(line.debit, 0.0, precision_rounding=0.01) > 0
            and line.account_id.id
            in (self.factor_transfer_id.journal_id.factor_holdback_account_id.id,)
            and not line.reconciled
        )
        # getting the % holdback this way ensure it can easily be reconciled
        invoice_holdback = sum(lines.mapped("debit"))
        initial_balance_journal = self.factor_transfer_id.with_context(
            {"compute_factor_partner": self.partner_id}
        ).journal_id

        customer_balance = (
            initial_balance_journal.factor_customer_credit - self.amount_total
        )  # DIFFERENT FROM account_payment !!
        initial_holdback = initial_balance_journal.factor_holdback_balance
        initial_limit_holdback = initial_balance_journal.factor_limit_holdback_balance

        # REA = encours - limit - holback_balance - limit_holdback_balance
        limit_holdback = self.currency_id.round(
            customer_balance
            - self.partner_id.factor_credit_limit
            - initial_holdback
            + invoice_holdback
        )

        dg = self.currency_id.rounding
        if float_compare(limit_holdback, 0.0, precision_rounding=dg) < 0:
            limit_holdback = 0
        if initial_limit_holdback > limit_holdback:
            limit_holdback_to_free = initial_limit_holdback - limit_holdback
        else:
            limit_holdback_to_free = 0

        if float_compare(limit_holdback_to_free, 0.0, precision_rounding=dg) > 0:
            holdback_total = invoice_holdback + limit_holdback_to_free
        else:
            holdback_total = invoice_holdback

        payment_vals_list = [
            (
                0,
                0,
                {
                    "name": "%s - %s" % (_("Payment"), self.partner_id.name),
                    # 'date_maturity': fields.Date.context_today(),
                    "amount_currency": holdback_total,
                    "currency_id": self.currency_id.id,
                    "debit": holdback_total,
                    "credit": 0.0,
                    "partner_id": self.partner_id.id,
                    "account_id": self.factor_transfer_id.journal_id.default_account_id.id,
                },
            ),
        ]

        if float_compare(limit_holdback_to_free, 0.0, precision_rounding=dg) > 0:
            acc_id = (
                self.factor_transfer_id.journal_id.factor_limit_holdback_account_id.id
            )
            payment_vals_list.append(
                (
                    0,
                    0,
                    {
                        "name": "%s - %s" % (_("Payment"), self.partner_id.name),
                        # 'date_maturity': fields.Date.context_today(),
                        "amount_currency": limit_holdback_to_free,
                        "currency_id": self.currency_id.id,
                        "debit": 0.0,
                        "credit": limit_holdback_to_free,
                        "partner_id": self.partner_id.id,
                        "account_id": acc_id,
                    },
                )
            )

        for line in lines:
            payment_vals_list.append(
                (
                    0,
                    0,
                    {
                        "name": "%s - %s" % (_("Payment"), self.partner_id.name),
                        # 'date_maturity': fields.Date.context_today(),
                        "amount_currency": line.debit,
                        "currency_id": self.currency_id.id,
                        "debit": 0.0,
                        "credit": line.debit,
                        "partner_id": self.partner_id.id,
                        "account_id": line.account_id.id,
                    },
                )
            )

        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_id": self.partner_id.id,
                "currency_id": self.currency_id.id,
                # 'partner_bank_id': pay.partner_bank_id.id,
                "line_ids": payment_vals_list,
            }
        )
        self.factor_payment_id = payment.move_id.id
        # TODO study if we could leave the payment move in draft for
        # manual validation eventually (then reconciliation should be automated)
        payment.action_post()

        # now we reconcile the % holdback release:
        domain = [
            ("account_internal_type", "=", "other"),
            ("reconciled", "=", False),
            ("credit", ">", 0),
        ]
        payment_lines = payment.line_ids.filtered_domain(domain)
        (payment_lines + lines).filtered_domain(
            [
                (
                    "account_id",
                    "=",
                    self.factor_transfer_id.journal_id.factor_holdback_account_id.id,
                ),
                ("reconciled", "=", False),
            ]
        ).with_context({"skip_account_move_synchronization": True}).reconcile()

        # now we try to reconcile limit holdback lines:
        # required to test if limit_holdback is zero later
        self.env.cr.commit()  # pylint: disable=invalid-commit
        self.env["account.journal"].flush(["factor_limit_holdback_balance"])
        balance_journal = self.factor_transfer_id.with_context(
            {"compute_factor_partner": self.partner_id}
        ).journal_id
        if float_is_zero(
            balance_journal.factor_limit_holdback_balance, 0.0, precision_rounding=dg
        ):
            open_limit_holdback_lines = self.env["account.move.line"].search(
                [
                    (
                        "account_id",
                        "=",
                        self.factor_transfer_id.journal_id.factor_limit_holdback_account_id.id,
                    ),
                    ("partner_id", "=", self.partner_id.id),
                    ("parent_state", "=", "posted"),
                    ("reconciled", "=", False),
                ]
            )
            open_limit_holdback_lines.with_context(
                {"skip_account_move_synchronization": True}
            ).reconcile()

        self.payment_state_with_factor = "factor_paid"

    def button_cancel_factor(self):
        for inv in self:
            if inv.factor_payment_id:
                inv.factor_payment_id.button_cancel()
                inv.factor_payment_id.mapped("line_ids").remove_move_reconcile()
            if inv.factor_transfer_id and inv.factor_transfer_id.state in (
                "draft",
                "posted",
            ):
                inv.factor_transfer_id.button_cancel()
                inv.factor_transfer_id.mapped("line_ids").remove_move_reconcile()
                inv.payment_state = "not_paid"
                inv.payment_mode_id = False
