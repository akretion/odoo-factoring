# © 2022 David BEAL @ Akretion
# © 2022 Alexis DE LATTRE @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError, RedirectWarning


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
    date = fields.Date(
        string="Confirmed Date",
        readonly=True,
        tracking=True,
    )
    statement_date = fields.Date(
        help="Date of the last bank statement taken account in accounting"
    )

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
        comodel_name="res.company", string="Company", readonly=True, required=True
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
            ("company_id", "=", self.env.company.id),
            ("subrogation_id", "=", False),
            ("state", "=", "posted"),
            "|",
            "&",
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("payment_state", "not in", ("paid", "invoicing_legacy")),
            "&",
            ("move_type", "=", "misc"),
            ("line_ids.account_id.group_id", "=", self.env.ref("l10n_fr.1_pcg_411").id),
        ]
        if partner_selection_field:
            res.append(
                (
                    "partner_id.commercial_partner_id.%s" % partner_selection_field,
                    "=",
                    True,
                )
            )
        return res

    def _prepare_factor_file(self, factor_type):
        self.ensure_one
        method = "_prepare_factor_file_%s" % factor_type
        if hasattr(self, method):
            return getattr(self, method)()
        else:
            pass

    def action_confirm(self):
        for rec in self:
            if rec.state == "draft":
                rec.state = "confirmed"
                rec.date = fields.Date.today()
                data = self._prepare_factor_file(rec.factor_type)
                if data:
                    self.env["ir.attachment"].create(data)

    def action_post(self):
        for rec in self:
            if (
                rec.state == "confirmed"
                and rec.holdback_amount > 0
                and rec.expense_untaxed_amount > 0
                and rec.expense_tax_amount > 0
            ):
                rec.state = "posted"
            else:
                raise UserError(
                    _(
                        "Check fields 'Holdabck Amount', 'Untaxed Amount', "
                        "'Tax Amount', they should have a value"
                    )
                )

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
                _(
                    "You must configure journal according to factor and currency.\n"
                    "Click on 'Configure journals and accounts' "
                    "in company page, 'Factor' tab"
                )
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
                "view_id": self.env.ref(
                    "account_factoring_receivable_balance.subrogation_receipt_tree"
                ).id,
            }
        else:
            message = (
                "No invoice needs to be linked to a Factor '%s'.\n"
                "Check matching customers or invoices state." % factor_type
            )
            raise RedirectWarning(
                _(message),
                self.env.ref("account.action_move_out_invoice_type").id,
                _("See invoices and customers"),
            )

    def _sanitize_filepath(self, string):
        "Helper to make safe filepath"
        for elm in ["/", " ", ":", "<", ">", "\\", "|", "?", "*"]:
            string = string.replace(elm, "_")
        return string
