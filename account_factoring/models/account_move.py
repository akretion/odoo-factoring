# Copyright (C) 2021 - TODAY Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, api, fields, models
from odoo.tools import float_compare, float_is_zero


class AccountMove(models.Model):
    _inherit = "account.move"

    # new state capturing the factoring state.
    # we avoid touching the original payment_state to avoid side effects
    payment_state_with_factor = fields.Selection(
        selection=[
            ("not_paid", "Not Paid"),
            ("to_transfer_to_factor", "To Transfer to Factor"),  # added for factoring
            ("transferred_to_factor", "Transferred to Factor"),  # added for factoring
            ("factor_paid", "Factor Paid"),  # added for factoring
            ("in_payment", "In Payment"),
            ("paid", "Paid"),
            ("partial", "Partially Paid"),
            ("reversed", "Reversed"),
            ("invoicing_legacy", "Invoicing App Legacy"),
        ],
        string="Payment Status",
        store=True,
        readonly=True,
        copy=False,
        tracking=True,
        help="payment status with factor",
        compute="_compute_payment_state_with_factor",
    )

    factor_transfer_id = fields.Many2one(
        "account.move", compute="_compute_factor_transfer_id"
    )
    factor_payment_id = fields.Many2one(
        "account.move", compute="_compute_factor_payment_id"
    )

    @api.depends("payment_state", "payment_mode_id")
    def _compute_payment_state_with_factor(self):
        for move in self:
            if (
                move.move_type == "out_invoice"
                and move.payment_mode_id
                and move.payment_mode_id.fixed_journal_id
                and move.payment_mode_id.fixed_journal_id.is_factor
            ):
                if move.payment_state == "not_paid" and move.state != "cancel":
                    move.payment_state_with_factor = "to_transfer_to_factor"
                elif move.payment_state == "paid":
                    move.payment_state_with_factor = "transferred_to_factor"
                else:
                    move.payment_state_with_factor = move.payment_state
            else:
                move.payment_state_with_factor = move.payment_state

    def _compute_factor_transfer_id(self):
        for inv in self:
            factor_transfers = (
                inv.mapped("line_ids")
                .mapped("full_reconcile_id")
                .reconciled_line_ids.mapped("move_id")
                .filtered(
                    lambda move: move.id not in self.ids and move.state != "cancel"
                )
            )
            if factor_transfers:
                inv.factor_transfer_id = factor_transfers[0]
            else:
                inv.factor_transfer_id = False

    def _compute_factor_payment_id(self):
        for inv in self:
            factor_payments = (
                inv.factor_transfer_id.mapped("line_ids")
                .filtered(
                    lambda line: line.account_id
                    == inv.factor_transfer_id.journal_id.factor_holdback_account_id
                )
                .mapped("full_reconcile_id")
                .reconciled_line_ids.mapped("move_id")
                .filtered(
                    lambda move: move.id not in self.factor_transfer_id.ids
                    and move.state != "cancel"
                )
            )
            if factor_payments:
                inv.factor_payment_id = factor_payments[0]
            else:
                inv.factor_payment_id = False

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

    def button_factor_paid(self):
        """
        Compute the proper holdback amounts to release.
        The holdback proportional to the invoice amount is always fully
        released and reconciled with the transfer holdback. The limit holdback
        is more subtle to release.
        """
        self.ensure_one()
        lines = self.factor_transfer_id.line_ids.filtered(
            lambda line: float_compare(line.debit, 0.0, precision_rounding=0.01) > 0
            and line.account_id.id
            in (self.factor_transfer_id.journal_id.factor_holdback_account_id.id,)
            and not line.reconciled
        )
        # getting the % holdback this way ensure it can easily be reconciled
        invoice_holdback = sum(lines.mapped("debit"))
        initial_balance_journal = (
            lines[0]
            .move_id.with_context({"compute_factor_partner": self.partner_id})
            .journal_id
        )

        dg = self.currency_id.rounding
        initial_balance_journal = (
            lines[0]
            .move_id.with_context({"compute_factor_partner": self.partner_id})
            .journal_id
        )
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
                        "account_id": self.factor_transfer_id.journal_id.factor_limit_holdback_account_id.id,
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
        self.env.cr.commit()  # required to test if imit_holdback is zero later
        self.env["account.journal"].flush(["factor_limit_holdback_balance"])
        balance_journal = (
            lines[0]
            .move_id.with_context({"compute_factor_partner": self.partner_id})
            .journal_id
        )
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
