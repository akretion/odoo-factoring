# © 2023 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    subrogation_id = fields.Many2one(
        comodel_name="subrogation.receipt",
        string="Subrogation Receipt",
        check_company=True,
        help="Used if you want to create from journal entries from a posted "
        "Subrogation Receipt",
    )
    skip_factor = fields.Boolean(
        help="Prevent this document to be taken in account in factor current selection"
    )
    use_factor = fields.Boolean(
        compute="_compute_use_factor",
        help="Depending on partner factor settings and skip factor field",
        store=True,
    )
    factor_journal_id = fields.Many2one(
        comodel_name="account.journal",
        related="commercial_partner_id.factor_journal_id",
        store=False,
    )

    @api.depends(
        "factor_journal_id",
        "factor_journal_id.factor_start_date",
        "factor_journal_id.factor_invoice_journal_ids",
    )
    def _compute_use_factor(self):
        for rec in self:
            use_factor = False
            rec = rec.with_company(rec.company_id.id)
            if rec.id and rec.factor_journal_id:
                # TODO replace by adhoc odoo method : domain to python expression
                domain = rec.factor_journal_id._get_domain_for_factor()
                domain.extend([("id", "=", rec.id), ("skip_factor", "=", False)])
                if rec.search(domain):
                    use_factor = True
            rec.use_factor = use_factor
