# © 2024 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, exceptions, fields, models


def ini_format_to_dict(multiline_text):
    vals = {}
    for row in multiline_text.strip().split("\n"):
        if "=" in row and row[0] != "#":
            key, val = row.split("=")
            if "#" in val:
                val, __ = val.split("#")
            vals[key.strip(" ")] = val.strip(" ")
    return vals


class AccountJournal(models.Model):
    _inherit = "account.journal"

    factor_type = fields.Selection(
        selection_add=[("eurof", "Eurofactor")],
        ondelete={"eurof": "set null"},
    )
    factor_data = fields.Text(
        default="\nkey1 = value1 \nkey2 = value2  # comment",
        help="A saisir dans ce champ des clés / valeurs séparées par des =",
    )
    factor_settings = fields.Char(compute="_compute_factor_settings")

    @api.depends("factor_data")
    def _compute_factor_settings(self):
        for rec in self:
            try:
                rec.factor_settings = ini_format_to_dict(rec.factor_data)
            except Exception:
                raise exceptions.ValidationError(
                    f"Le format des data\n{rec.factor_data}\nn'est pas conforme"
                ) from None
