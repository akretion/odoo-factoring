# © 2023 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .subrogation_receipt import journal_domain


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

    def _is_factor_eligible(self):
        self.ensure_one()
        journal_id = journal_domain(self)
        if journal_id:
            domain = self.env["account.move.line"]._get_domain_for_factor(
                journal=self.env["account.journal"].browse(journal_id)
            )
            lines = self.line_ids.filtered_domain(
                [self.env["account.move.line"]._get_customer_accounts()]
            )
            if not lines:
                raise UserError(_("No line for 'asset_receivable' account kind"))
            members = []

            def resolve_field_value(previous_value, ffield):
                new_field_value = getattr(previous_value, ffield)
                if not new_field_value:
                    new_field_value = False
                return new_field_value

            for elm in domain:
                field_parts = elm[0].split(".")
                res = lines[0]
                for part in field_parts:
                    res = resolve_field_value(res, part)
                members.append(f"{elm[0]}: {res}")
            raise UserError(
                _(f"Domain is\n{domain}\n\nCurrent record:\n{' ; '.join(members)}")
            )
        else:
            raise UserError(_("Several factor journals : unsupported case"))
