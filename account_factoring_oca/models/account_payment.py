# Copyright (C) 2021 - TODAY Raphaël Valyi - Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.tools import float_compare


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _prepare_move_withholding_lines(self, default_values):
        """Inject factoring fees and holdbacks as withholding lines.
        Odoo 18 will automatically deduct these from the liquidity line balance.
        """
        res = super()._prepare_move_withholding_lines(default_values)

        if not self.journal_id.is_factor or self.payment_type != "inbound":
            return res

        self.ensure_one()
        dg = self.currency_id.rounding
        company_currency = self.company_id.currency_id

        # Logic for amounts calculation
        amount = self.amount
        factor_fee_amount = self.currency_id.round(
            amount * self.journal_id.factor_fee / 100.0
        )

        # Calculate Tax on Fee
        factor_fee_tax_amount = 0.0
        fee_tax_account_id = False
        if self.journal_id.factor_tax_id:
            factor_fee_tax_amount = self.currency_id.round(
                factor_fee_amount * self.journal_id.factor_tax_id.amount / 100.0
            )
            tax_repartition = (
                self.journal_id.factor_tax_id.invoice_repartition_line_ids.filtered(
                    lambda line: line.repartition_type == "tax"
                )
            )
            if tax_repartition:
                fee_tax_account_id = tax_repartition[0].account_id.id

        # Standard Holdback %
        invoice_holdback = self.currency_id.round(
            amount * self.journal_id.factor_holdback_percent / 100.0
        )

        # Limit Holdback Logic
        initial_balance_journal = self.with_context(
            compute_factor_partner=self.partner_id
        ).journal_id

        customer_balance = initial_balance_journal.factor_customer_credit
        initial_holdback = initial_balance_journal.factor_holdback_balance
        initial_limit_holdback = initial_balance_journal.factor_limit_holdback_balance

        limit_holdback = self.currency_id.round(
            customer_balance
            - (self.partner_id.factor_credit_limit or 0.0)
            - initial_holdback
            - invoice_holdback
            - initial_limit_holdback
            - factor_fee_amount
            - factor_fee_tax_amount
        )

        if (
            float_compare(limit_holdback, 0.0, precision_rounding=dg) < 0
            or not self.partner_id.factor_credit_limit
        ):
            limit_holdback = 0.0

        # Prepare withholding dictionaries
        withholding_configs = [
            (
                factor_fee_amount,
                self.journal_id.factor_fee_account_id.id,
                self.env._("Factor Fee"),
            ),
            (factor_fee_tax_amount, fee_tax_account_id, self.env._("Factor Fee Tax")),
            (
                invoice_holdback,
                self.journal_id.factor_holdback_account_id.id,
                self.env._("Holdback"),
            ),
            (
                limit_holdback,
                self.journal_id.factor_limit_holdback_account_id.id,
                self.env._("Limit Holdback"),
            ),
        ]

        for amt, acc_id, label in withholding_configs:
            if float_compare(amt, 0.0, precision_rounding=dg) > 0 and acc_id:
                res.append(
                    {
                        "name": f"{label} - {self.name}",
                        "account_id": acc_id,
                        "amount_currency": amt,
                        "balance": self.currency_id._convert(
                            amt, company_currency, self.company_id, self.date
                        ),
                        "currency_id": self.currency_id.id,
                        "partner_id": self.partner_id.id,
                    }
                )

        return res

    def _prepare_move_liquidity_lines(self, default_values):
        """Ensure the correct liquidity account is used for factor journals."""
        res = super()._prepare_move_liquidity_lines(default_values)

        if self.journal_id.is_factor:
            # For factoring, we often force the use of the default account
            # instead of outstanding accounts for specific transfer types
            for line in res:
                line["account_id"] = self.journal_id.default_account_id.id

        return res
