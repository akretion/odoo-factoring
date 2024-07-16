# © 2022 David BEAL @ Akretion
# © 2022 Alexis DE LATTRE @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

from odoo import fields, models

logger = logging.getLogger(__name__)

logger.warning(
    "\n\n\n     ACHTUNG !!!!!! This module'll have breaking changes in next weeks\n\n"
)
logger.warning(
    "\n\n   Consider to check https://github.com/akretion/odoo-factoring/pull/21\n\n"
)
logger.warning("\n\n         Drop a comment to flag you use this module\n\n")


class AccountJournal(models.Model):
    _inherit = "account.journal"

    factor_type = fields.Selection(string="Factor", selection_add=[("", "")])
    factoring_receivable_account_id = fields.Many2one(
        comodel_name="account.account", string="Receivable Account"
    )
    factoring_current_account_id = fields.Many2one(
        comodel_name="account.account", string="Current Account"
    )
    factoring_holdback_account_id = fields.Many2one(
        comodel_name="account.account", string="Holdback Account"
    )
    factoring_pending_recharging_account_id = fields.Many2one(
        comodel_name="account.account", string="Pending Recharging Account"
    )
    factoring_expense_account_id = fields.Many2one(
        comodel_name="account.account", string="Expense Account"
    )

    _sql_constraints = [
        (
            "currency_factor_curr_type_cpny_unique",
            "UNIQUE(currency_id, factor_type, type, company_id)",
            "Field Factor type must be unique by Currency, Journal type, and Company",
        )
    ]
