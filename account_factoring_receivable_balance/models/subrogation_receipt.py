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
                rec.date or rec.state,
            )

    @api.model
    def _get_moves_domain_for_factor(
        self, factor_type, account_group, partner_selection_field=None, currency=None
    ):
        """We separate domain in multi parts to avoid to compose
        over complicated queries"""
        bank_journal = self._get_bank_journal(factor_type, currency=currency)
        if not bank_journal:
            return False
        group_id = self.env.ref(account_group).id
        main = [
            ("company_id", "=", self.env.company.id),
            ("subrogation_id", "=", False),
            ("state", "=", "posted"),
        ]
        dom_inv = [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("payment_state", "not in", ("paid",)),
        ]
        if partner_selection_field:
            dom_inv.append(
                (
                    "partner_id.commercial_partner_id.%s" % partner_selection_field,
                    "=",
                    True,
                )
            )
        dom_misc = [
            ("move_type", "=", "misc"),
            ("line_ids.account_id.group_id", "=", group_id),
        ]
        dom_bk = [
            ("move_id.move_type", "=", "entry"),
            ("move_id.journal_id", "=", bank_journal.id),
            ("account_id.group_id", "=", group_id),
            ("full_reconcile_id", "=", False),
        ]
        main_line = [("%s.%s" % ("move_id", x[0]), x[1], x[2]) for x in main]
        return {
            "invoices": main + dom_inv,
            "misc": main + dom_misc,
            "bank": main_line + dom_bk,
        }

    @api.model
    def _create_or_update_subrogation_receipt(
        self, factor_type, account_group, partner_field=None
    ):
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
        subr_ids = []
        missing_journals = []
        for journal in journals:
            move_domains = self._get_moves_domain_for_factor(
                factor_type,
                account_group,
                partner_selection_field=partner_field,
                currency=journal.currency_id,
            )
            if not move_domains:
                missing_journals.append(journal)
                continue
            inv_moves = self.env["account.move"].search(
                move_domains["invoices"]
                + [("currency_id", "=", journal.currency_id.id)]
            )
            misc_moves = self.env["account.move"].search(
                move_domains["misc"] + [("currency_id", "=", journal.currency_id.id)]
            )
            move_lines = self.env["account.move.line"].search(
                move_domains["bank"]
                + [("move_id.currency_id", "=", journal.currency_id.id)]
            )
            bank_moves = move_lines.mapped("move_id")
            moves = inv_moves | misc_moves | bank_moves
            if not moves:
                continue
            self.search(
                [("factor_journal_id", "=", journal.id), ("state", "=", "draft")]
            ).unlink()
            subrog = self.create(
                {
                    "factor_journal_id": journal.id,
                    "company_id": journal.company_id.id,
                }
            )
            subr_ids.append(subrog.id)
            moves.write({"subrogation_id": subrog.id})
        if subr_ids:
            action = {
                "name": _("Generated Subrogation"),
                "res_model": "subrogation.receipt",
                "view_mode": "tree,form",
                "domain": "[('id', 'in', %s)]" % subr_ids,
                "type": "ir.actions.act_window",
                "target": "new",
                "view_id": self.env.ref(
                    "account_factoring_receivable_balance.subrogation_receipt_tree"
                ).id,
            }
            if missing_journals:
                message = (
                    "Missing bank journal for %s and currency %s to finish process"
                    % (
                        factor_type,
                        missing_journals[0].currency_id.name,
                    )
                )
                action = self.env[action["type"]].create(action)
                raise RedirectWarning(
                    _(message), action.id, _("See created subrogations")
                )
            return action
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

    def _get_bank_journal(self, factor_type, currency=None):
        """Get matching bank journal
        You may override to have a dedicated mapping"""
        domain = [("type", "=", "bank"), ("factor_type", "=", factor_type)]
        if currency:
            domain += [("currency_id", "=", currency.id)]
        return self.env["account.journal"].search(domain, limit=1)

    def _prepare_factor_file(self, factor_type):
        self.ensure_one
        method = "_prepare_factor_file_%s" % factor_type
        if hasattr(self, method):
            return getattr(self, method)()
        else:
            pass

    def _sanitize_filepath(self, string):
        "Helper to make safe filepath"
        for elm in ["/", " ", ":", "<", ">", "\\", "|", "?", "*"]:
            string = string.replace(elm, "_")
        return string

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

    def action_goto_moves(self):
        self.ensure_one()
        return {
            "name": _("Subrogation Receipt %s" % self.display_name),
            "res_model": "account.move",
            "view_mode": "tree,form",
            "domain": "[('subrogation_id', '=', %s)]" % self.id,
            "type": "ir.actions.act_window",
        }
