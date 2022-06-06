# © 2022 David BEAL @ Akretion
# © 2022 Alexis DE LATTRE @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools.misc import formatLang, format_date as odoo_format_date, get_lang


class SubrogationReceipt(models.Model):
    _name = "subrogation.receipt"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _check_company_auto = True
    _rec_name = "factor_type"
    _description = "Contains data relative to sent balance to factoring"

    factor_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Journal",
        domain="[('factor_type', '!=', False)]",
        check_company=True,
        required=True,
    )
    factor_type = fields.Selection(related="factor_journal_id.factor_type", store=True)
    currency_id = fields.Many2one(related="factor_journal_id.currency_id", store=True)
    display_name = fields.Char(compute="_compute_display_name")
    date = fields.Date(string="Confirmed Date", readonly=True)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("posted", "Posted"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    expense_untaxed_amount = fields.Float(tracking=True, help="")
    expense_tax_amount = fields.Float(tracking=True, help="")
    holdback_amount = fields.Float(tracking=True, help="")
    company_id = fields.Many2one(
        comodel_name="res.company", string="Company", required=True
    )
    move_ids = fields.One2many(
        comodel_name="account.move",
        inverse_name="subrogation_id",
        readonly=True,
    )

    @api.depends("factor_journal_id", "date")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s %s %s" % (
                rec.factor_type,
                rec.currency_id.name,
                rec.date or "",
            )

    @api.model
    def _get_moves_domain_for_factor(self, partner_selection_field=None):
        res = [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("subrogation_id", "=", False),
            ("state", "=", "posted"),
            ("company_id", "=", self.env.company.id),
        ]
        if partner_selection_field:
            res.append(("partner_id.%s" % partner_selection_field, "=", True))
        return res

    @api.model
    def _create_or_update_subrogation_receipt(self, factor_type, partner_field=None):
        journals = self.env["account.journal"].search(
            [
                ("factor_type", "=", factor_type),
                ("company_id", "=", self.env.company.id),
            ]
        )
        if not journals:
            raise UserError(
                _("You must configure journal according to factor and currency")
            )
        moves_domain = self._get_moves_domain_for_factor(
            partner_selection_field=partner_field
        )
        subr_ids = []
        for journal in journals:
            moves = self.env["account.move"].search(
                moves_domain + [("currency_id", "=", journal.currency_id.id)]
            )
            if not moves:
                continue
            # Journal constraint ensure to only have 1 journal by currency
            subrog = self.search(
                [("factor_journal_id", "=", journal.id), ("state", "=", "draft")]
            )
            if not subrog:
                subrog = self.create(
                    {
                        "factor_journal_id": journal.id,
                        "company_id": journal.company_id.id,
                    }
                )
                subr_ids.append(subrog.id)
            moves.write({"subrogation_id": subrog.id})
        if subr_ids:
            return {
                "name": _("Generated Subrogation"),
                "res_model": "subrogation.receipt",
                "view_mode": "tree,form",
                "domain": "[('id', 'in', %s)]" % subr_ids,
                "type": "ir.actions.act_window",
                "view_id": self.env.ref("account_factoring_receivable_balance.subrogation_receipt_tree").id,
            }            
        else:
            raise UserError(
                _(
                    "No invoice needs to be linked to a Factor Subrogation Receipt.\n"
                    "Check matching csutomers or invoices state."
                )
            )
