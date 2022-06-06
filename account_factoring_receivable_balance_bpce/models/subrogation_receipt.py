# © 2022 David BEAL @ Akretion
# © 2022 Alexis DE LATTRE @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools.misc import formatLang, format_date as odoo_format_date, get_lang


class SubrogationReceipt(models.Model):
    _inherit = "subrogation.receipt"
