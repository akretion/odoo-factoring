# © 2022 David BEAL @ Akretion
# © 2022 Alexis DE LATTRE @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    subrogation_id = fields.Many2one(
        comodel_name="subrogation.receipt",
        string="Subrogation Receipt",
        check_company=True,
    )
    subro_id = fields.Many2one(
        comodel_name="subrogation.receipt",
        string="Subrogation Group",
        help="Duplicate of the technical field 'Subrogation Receipt' to be able "
        "to group journal items according to Subrogations",
    )
    bank_id = fields.Many2one(
        comodel_name="res.bank",
        related="move_id.partner_bank_id.bank_id",
        string="Recipient Bank",
        help="Bank of the partner",
    )
