# © 2022 David BEAL @ Akretion
# © 2022 Alexis DE LATTRE @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools.misc import formatLang, format_date as odoo_format_date, get_lang


class ResPartner(models.Model):
    _inherit = "res.partner"

    bpce_factoring_balance = fields.Boolean(
        string="Use BPCE factoring balance",
        groups="account.group_account_invoice",
        company_dependent=True,
        help="Use BPCE factoring receivable balance external service",
    )
