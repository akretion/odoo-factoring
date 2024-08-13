# © 2024 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    factor_type = fields.Selection(
        selection_add=[("eurof", "Eurofactor")],
        ondelete={"eurof": "set null"},
    )
    factor_code2 = fields.Char(
        help="Numéro attribué par notre système à l’enregistrement de votre contrat",
    )
