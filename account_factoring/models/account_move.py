# Copyright (C) 2021 - TODAY Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, api, fields, models
from odoo.tools import float_compare


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

    factor_transfer_id = fields.Many2one("account.move", compute="_compute_factor_transfer_id")
    factor_payment_id = fields.Many2one("account.move", compute="_compute_factor_payment_id")

    @api.depends("payment_state", "payment_mode_id")
    def _compute_payment_state_with_factor(self):
        for move in self:
            # TODO what if the journal was changed in the payment wizard?
            if (
                move.move_type == "out_invoice"
                and move.payment_mode_id
                and move.payment_mode_id.fixed_journal_id
                and move.payment_mode_id.fixed_journal_id.is_factor
            ):
                if move.payment_state == "not_paid":
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
                    lambda move: move.id not in self.ids
                    and move.state != 'cancel'
                )
            )
            if factor_transfers:
                inv.factor_transfer_id = factor_transfers[0]
            else:
                inv.factor_transfer_id = False

    def _compute_factor_payment_id(self):
        for inv in self:
            factor_payments = (
                inv.factor_transfer_id.mapped("line_ids").filtered(
                    lambda line: line.account_id == inv.factor_transfer_id.journal_id.factor_holdback_account_id
                ).mapped("full_reconcile_id")
                .reconciled_line_ids.mapped("move_id")
                .filtered(
                    lambda move: move.id not in self.factor_transfer_id.ids
                    and move.state != 'cancel'
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
        self.ensure_one()
        lines = self.factor_transfer_id.line_ids.filtered(
            lambda line: float_compare(line.debit, 0.0, precision_rounding=0.01) > 0
            and line.account_id.id
            in (
                self.factor_transfer_id.journal_id.factor_holdback_account_id.id,
                self.factor_transfer_id.journal_id.factor_limit_holdback_account_id.id,
            )
            and not line.reconciled
        )
        total = sum(lines.mapped("debit"))
        print("TO RECONCILE", lines, total)
        payment_vals_list = [
            (
                0,
                0,
                {
                    "name": "%s - %s" % (_("Payment"), self.partner_id.name),
                    # 'date_maturity': fields.Date.context_today(),
                    "amount_currency": total,
                    "currency_id": self.currency_id.id,
                    "debit": total,
                    "credit": 0.0,
                    "partner_id": self.partner_id.id,
                    "account_id": self.factor_transfer_id.journal_id.default_account_id.id,
                },
            ),
        ]

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
        print("payment_vals_list", payment_vals_list)
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
        print("payment", payment.id, payment.state)
        domain = [
            ("account_internal_type", "=", "other"),
            ("reconciled", "=", False),
            ("credit", ">", 0),
        ]

        payment_lines = payment.line_ids.filtered_domain(domain)
        print("payment_lines", payment_lines)
        for account in payment_lines.mapped("account_id"):
            print(
                "REC",
                payment_lines + lines,
                (payment_lines + lines).filtered_domain(
                    [("account_id", "=", account.id), ("reconciled", "=", False)]
                ),
            )
            (payment_lines + lines).filtered_domain(
                [("account_id", "=", account.id), ("reconciled", "=", False)]
            ).with_context({"skip_account_move_synchronization": True}).reconcile()

        self.payment_state_with_factor = "factor_paid"
