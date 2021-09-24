# Copyright (C) 2021 - TODAY Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, models
from odoo.tools import float_compare


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        self.ensure_one()
        line_vals = super()._prepare_move_line_default_vals(write_off_line_vals)
        if self.payment_type == "inbound" and self.journal_id.is_factor:
            line_vals = self._inject_factor_credit_transfer_lines(line_vals)
        return line_vals

    def _inject_factor_credit_transfer_lines(self, line_vals):
        self.ensure_one()
        original_liquidity_line = False
        new_line_vals = []
        for line in line_vals:
            account = self.env["account.account"].browse(line["account_id"])
            # checking the account should avoid taking a write off line:
            if (
                account.internal_type == "other"
                and account.internal_group == "asset"
                and line["debit"] > 0.0
            ):
                original_liquidity_line = line
            else:
                new_line_vals.append(line)

        if not original_liquidity_line:
            return line_vals

        amount = original_liquidity_line["debit"]
        factor_fee_amount = self.currency_id.round(
            amount * self.journal_id.factor_fee / 100.0
        )
        factor_fee_tax_amount = self.currency_id.round(
            factor_fee_amount * self.journal_id.factor_tax_id.amount / 100.0
        )

        invoice_holdback = self.currency_id.round(
            amount * self.journal_id.factor_holdback_percent / 100.0
        )

        dg = self.currency_id.rounding

        initial_balance_journal = self.with_context(
            {"compute_factor_partner": self.partner_id}
        ).journal_id
        customer_balance = initial_balance_journal.factor_customer_credit
        initial_holdback = initial_balance_journal.factor_holdback_balance
        initial_limit_holdback= initial_balance_journal.factor_limit_holdback_balance

        limit_holdback = self.currency_id.round(
            customer_balance
            - self.partner_id.factor_credit_limit
            - initial_holdback
            - invoice_holdback
            - initial_limit_holdback
            - factor_fee_amount
            - factor_fee_tax_amount
        )

        if float_compare(limit_holdback, 0.0, precision_rounding=dg) < 0:
            limit_holdback = 0

        # TODO limit_holdback can also be 0 under other conditions
        # such as customer_balance < 40% of total factor_balance...

        remaining_amount = self.currency_id.round(
            original_liquidity_line["debit"]
            - factor_fee_amount
            - factor_fee_tax_amount
            - invoice_holdback
            - limit_holdback
        )

        liquidity_lines = []

        if float_compare(remaining_amount, 0.0, precision_rounding=dg) > 0:
            liquidity_lines.append(
                {
                    "name": "%s - %s"
                    % (_("Factor Credit Transfer"), original_liquidity_line["name"]),
                    "date_maturity": original_liquidity_line["date_maturity"],
                    "amount_currency": remaining_amount,
                    "currency_id": original_liquidity_line["currency_id"],
                    "debit": remaining_amount,
                    "credit": 0.0,
                    "partner_id": original_liquidity_line["partner_id"],
                    "account_id": self.journal_id.default_account_id.id,
                }
            )
        elif float_compare(limit_holdback + remaining_amount, 0, precision_rounding=dg) > 0:
            # the factor customer balance is such that all money is holded back.
            # (remaining_amount is negative)
            # now we should make sure that we don't holdback more than the max possible:
            limit_holdback += remaining_amount


        if float_compare(factor_fee_amount, 0.0, precision_rounding=dg) > 0:
            liquidity_lines.append(
                {
                    "name": "%s - %s"
                    % (_("Factor Fee"), original_liquidity_line["name"]),
                    "date_maturity": original_liquidity_line["date_maturity"],
                    "amount_currency": factor_fee_amount,
                    "currency_id": original_liquidity_line["currency_id"],
                    "debit": factor_fee_amount,
                    "credit": 0.0,
                    "partner_id": original_liquidity_line[
                        "partner_id"
                    ],
                    "account_id": self.journal_id.factor_fee_account_id.id,
                }
            )

        if float_compare(factor_fee_tax_amount, 0.0, precision_rounding=dg) > 0:
            fee_tax_account = (
                self.journal_id.factor_tax_id.invoice_repartition_line_ids.filtered(
                    lambda line: line.repartition_type == "tax"
                )[0].account_id
            )
            liquidity_lines.append(  # TODO fill tax_tag_ids?
                {
                    "name": "%s - %s"
                    % (_("Factor Fee Tax"), original_liquidity_line["name"]),
                    "date_maturity": original_liquidity_line["date_maturity"],
                    "amount_currency": factor_fee_tax_amount,
                    "currency_id": original_liquidity_line["currency_id"],
                    "debit": factor_fee_tax_amount,
                    "credit": 0.0,
                    "partner_id": original_liquidity_line[
                        "partner_id"
                    ],
                    "account_id": fee_tax_account.id,
                }
            )

        if float_compare(invoice_holdback, 0.0, precision_rounding=dg) > 0:
            liquidity_lines.append(
                {
                    "name": "%s%% %s - %s"
                    % (
                        self.journal_id.factor_holdback_percent,
                        _("Holdback"),
                        original_liquidity_line["name"],
                    ),
                    "date_maturity": original_liquidity_line["date_maturity"],
                    "amount_currency": invoice_holdback,
                    "currency_id": original_liquidity_line["currency_id"],
                    "debit": invoice_holdback,
                    "credit": 0.0,
                    "partner_id": original_liquidity_line[
                        "partner_id"
                    ],
                    "account_id": self.journal_id.factor_holdback_account_id.id,
                }
            )

        if float_compare(limit_holdback, 0.0, precision_rounding=dg) > 0:
            liquidity_lines.append(
                {
                    "name": "%s - %s"
                    % (_("Limit Holdback"), original_liquidity_line["name"]),
                    "date_maturity": original_liquidity_line["date_maturity"],
                    "amount_currency": limit_holdback,
                    "currency_id": original_liquidity_line["currency_id"],
                    "debit": limit_holdback,
                    "credit": 0.0,
                    "partner_id": original_liquidity_line[
                        "partner_id"
                    ],
                    "account_id": self.journal_id.factor_limit_holdback_account_id.id,
                }
            )
        return liquidity_lines + new_line_vals

    def _synchronize_from_moves(self, changed_fields):
        """
        We skip the super move synchronization and do our own here
        """
        if self._context.get("factor_move_synchronization"):
            for pay in self.with_context(skip_account_move_synchronization=True):
                if pay.journal_id.is_factor:
                    # TODO adjust and test!
                    move = pay.move_id
                    payment_vals_to_write = {
                        # TODO ajust!
                        "amount": abs(liquidity_amount),
                        "partner_type": partner_type,
                        "currency_id": liquidity_lines.currency_id.id,
                        "destination_account_id": counterpart_lines.account_id.id,
                        "partner_id": liquidity_lines.partner_id.id,
                    }
                    pay.write(
                        move._cleanup_write_orm_values(pay, payment_vals_to_write)
                    )
        else:
            # if we did nothing bank statement transfer from factor to bank account would fail
            # because factor accounts are not receivable nor payable.
            context_dict = {}
            factor_accounts = set()
            for journal in self.env['account.journal'].search([
                ("is_factor", "=", True)
            ]):
                factor_accounts.add(journal.default_account_id)
                factor_accounts.add(journal.factor_holdback_account_id)
            for pay in self:
                for line in pay.line_ids:
                    if line.journal_id.type == "bank" and line.account_id in factor_accounts:
                        context_dict = {'skip_account_move_synchronization': True}
                        break
            return super(
                AccountPayment,
                self.with_context(context_dict)
            )._synchronize_from_moves(changed_fields)
