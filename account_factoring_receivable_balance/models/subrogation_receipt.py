# © 2022 David BEAL @ Akretion
# © 2022 Alexis DE LATTRE @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools.misc import formatLang, format_date as odoo_format_date, get_lang


class SubrogationReceipt(models.Model):
    _name = "subrogation.receipt"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Contains data relative to sent balance to factoring"

    factoring_journal_id = fields.Many2one(
        comodel_name="account.journal", string="Journal"
    )
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("posted", "Posted"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    expense_untaxed_amount = fields.Float(tracking=True, help="")
    expense_tax_amount = fields.Float(tracking=True, help="")
    holdback_amount = fields.Float(tracking=True, help="")
    move_ids = fields.One2many(
        comodel_name="account.move",
        inverse_name="subrogation_id",
        readonly=True,
        domain=[("move_type", "in", ("out_invoice", "out_refund"))],
    )
    # currency_id = fields.Many2one(
    #     comodel_name="res.currency",
    #     related="factoring_journal_id.currency_id",
    #     string="Currency",
    # )
