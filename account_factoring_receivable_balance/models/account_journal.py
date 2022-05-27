# © 2022 David BEAL @ Akretion
# © 2022 Alexis DE LATTRE @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools.misc import formatLang, format_date as odoo_format_date, get_lang


class AccountJournal(models.Model):
    _inherit = "account.journal"

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
