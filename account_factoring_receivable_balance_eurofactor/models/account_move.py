# © 2024 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _display_eurofactor_bank(self):
        "Used in report"
        self.ensure_one()
        self = self.with_company(self.company_id.id)
        if self.use_factor:
            return self.commercial_partner_id.factor_bank_id.display_name
        return ""


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

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
