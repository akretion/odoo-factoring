# © 2023 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    skip_factor = fields.Boolean(
        help="Prevent this document to be taken in account in factor current selection"
    )
    use_factor = fields.Boolean(
        compute="_compute_use_factor",
        help="Depending on partner factor settings and skip factor field",
    )
    factor_journal_id = fields.Many2one(
        comodel_name="account.journal",
        related="commercial_partner_id.factor_journal_id",
        store=False,
    )

    def _compute_use_factor(self):
        for rec in self:
            use_factor = False
            rec = rec.with_company(rec.company_id.id)
            factor_journal = rec.commercial_partner_id.factor_journal_id
            if factor_journal:
                # TODO replace by adhoc odoo method : domain to python expression
                domain = factor_journal._get_domain_for_factor()
                domain.extend([("id", "=", rec.id), ("skip_factor", "=", False)])
                if rec.search(domain):
                    use_factor = True
            rec.use_factor = use_factor
