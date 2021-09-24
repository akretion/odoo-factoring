# Copyright 2021 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    factor_credit_limit = fields.Monetary("Factor Credit Limit")

    factor_credit = fields.Monetary(
        compute="_compute_factor_data",
        string="Factor Credit",
        help="Total amount this customer owes to the factor.",
    )

    factor_holdback = fields.Monetary(
        compute="_compute_factor_data",
        string="Factor Holdback",
        help="Total factor holdback amount.",
    )

    def _compute_factor_data(self):
        for partner in self:
            journals = (
                self.env["account.journal"]
                .with_context({"compute_factor_partner": partner})
                .search([("is_factor", "=", True)])
            )
            partner.factor_credit = sum(journals.mapped("factor_customer_credit"))
            holdback = sum(journals.mapped("factor_holdback_balance"))
            limit_holdback = sum(journals.mapped("factor_limit_holdback_balance"))
            partner.factor_holdback = holdback + limit_holdback

    def open_customer_holdback(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_account_moves_all"
        )
        accounts = []
        for journal in self.env["account.journal"].search([("is_factor", "=", True)]):
            accounts.append(journal.factor_holdback_account_id.id)
            accounts.append(journal.factor_limit_holdback_account_id.id)
        action["domain"] = (
            "[('full_reconcile_id', '=', False), ('account_id', 'in', %s), ('partner_id', '=', %s)]"
            % (accounts, self.id)
        )
        return action
