# Copyright 2021 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    factor_credit_limit = fields.Monetary("Factor Credit Limit")

    # factor_credit = fields.Monetary(
    #     compute='_compute_factor_credit_debit',
    #     string='Factor Receivable',
    #     help="Total amount this customer owes to the factor."
    # )

    # factor_holdback_debit = fields.Monetary(
    #     compute='_compute_factor_holdback_amount',
    #     string='Computed Holdback Debit',
    # )

    # factor_holdback_credit = fields.Monetary(
    #     compute='_compute_factor_holdback_amount',
    #     string='Computed Holdback Credit',
    # )

    # factor_holdback_balance = fields.Monetary(
    #     compute='_compute_factor_holdback_amount',
    #     string='Computed Holdback Balance',
    # )

    # def _compute_factor_holdback_amount(self):
    #     self.factor_holdback_debit = 0
    #     self.factor_holdback_credit = 0
    #     self.factor_holdback_balance = 0
    #     account_ids = self.mapped('property_holdback_account_id').ids
    #     if not account_ids:
    #         return
    #     self.env.cr.execute("""
    #         SELECT line.account_id,
    #                SUM(line.balance) AS balance,
    #                SUM(line.debit) AS debit,
    #                SUM(line.credit) AS credit
    #         FROM account_move_line line
    #         WHERE line.account_id IN %s
    #         AND parent_state='posted'
    #         GROUP BY line.account_id
    #     """, [tuple(account_ids)])
    #     result = {r['account_id']: r for r in self.env.cr.dictfetchall()}
    #     for partner in self:
    #         res = result.get(partner.property_holdback_account_id.id) or {'debit': 0, 'credit': 0, 'balance': 0}
    #         partner.factor_holdback_debit = res['debit']
    #         partner.factor_holdback_credit = res['credit']
    #         partner.factor_holdback_balance = res['balance']

    # @api.depends_context('company')
    # def _compute_factor_credit_debit(self):
    #     for partner in self:
    #         partner.factor_credit = 42
    # TODO see https://github.com/odoo/odoo/blob/14.0/addons/account/models/partner.py#L240
