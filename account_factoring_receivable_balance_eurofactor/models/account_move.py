# © 2024 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _display_eurofactor_bank(self):
        "Used in report"
        self.ensure_one()
        self = self.with_company(self.company_id.id)
        if self.use_factor:
            return f"{self.commercial_partner_id.factor_bank_id.bank_id.display_name} - {self.commercial_partner_id.factor_bank_id.acc_number}"
        return ""


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    eurofactor_ref = fields.Char(related="partner_id.eurofactor_ref", string="Eurof")
    factor = fields.Char(string="Match", help="Utilisé pour faciliter le lettrage")

    def _eurof_fields_rpt(self):
        partner = self.partner_id.commercial_partner_id
        ref = partner._get_partner_eurof_mapping().get(partner, "")
        return {
            "Client": f"{ref}, {self.partner_id.name}",
            "Date": self.date,
            "Ecriture": self.name,
            "Debit": self.debit,
            "Credit": self.credit,
            "Echeance": self.move_id.invoice_date_due,
            "Origine": self.move_id.invoice_origin,
            "Devise": self.currency_id.name,
        }

    def _eurof_market(self, export=False):
        if export:
            return self.filtered(
                lambda s: s.move_id.commercial_partner_id.country_id
                != self.env.ref("base.fr")
            )
        return self.filtered(
            lambda s: s.move_id.commercial_partner_id.country_id
            == self.env.ref("base.fr")
        )
