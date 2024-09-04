# © 2024 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _display_eurofactor_bank(self):
        "Used in report"
        self.ensure_one()
        self = self.with_company(self.company_id.id)
        if self._use_factor():
            return self.commercial_partner_id.factor_bank_id.display_name
        return ""
