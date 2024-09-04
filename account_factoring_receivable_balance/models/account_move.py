# © 2023 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _use_factor(self):
        ""
        self.ensure_one()
        self = self.with_company(self.company_id.id)
        factor_journal = self.commercial_partner_id.factor_journal_id
        if factor_journal:
            # TODO replace by adhoc odoo method : domain to python expression
            domain = factor_journal._get_domain_for_factor()
            domain.append(("id", "=", self.id))
            if self.search(domain):
                return True
        return False


# env['account.move'].browse(26404)
