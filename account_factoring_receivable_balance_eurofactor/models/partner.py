# © 2024 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models

MODULE = __name__[12 : __name__.index(".", 13)]


class ResPartner(models.Model):
    _inherit = "res.partner"

    factor_bank_id = fields.Many2one(
        comodel_name="res.partner.bank",
        company_dependent=True,
        groups="account.group_account_manager",
    )

    def _get_partner_eurof_mapping(self):
        rec_categ = self.env.ref(f"{MODULE}.eurofactor_id_category")
        categ = self.env["res.partner.id_category"].search(
            [("code", "=", rec_categ.code)]
        )
        return {
            x.partner_id: x.name
            for x in self.env["res.partner.id_number"].search(
                [("category_id", "=", categ.id)]
            )
        }

    def _check_eurof_data(self):
        "Check data completude"

        def printit(records):
            return "\n" + "\n".join(records.mapped("display_name")) + "\n"

        bank_missings = self.filtered(lambda s: not s.factor_bank_id)
        if bank_missings:
            message = ""
            if bank_missings:
                message = (
                    f"Les clients {printit(bank_missings)}"
                    "n'ont pas de compte bancaire d'identifiant d'affacturage."
                )
            return message
