# Copyright (C) 2021 - TODAY Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    # settings fields:
    is_factor = fields.Boolean()
    factor_fee = fields.Float(string="Factor Fee %")
    factor_holdback_percent = fields.Float(string="Factor Holdback %")
    factor_partner_id = fields.Many2one(
        "res.partner",
        string="Factor Partner",
    )
    factor_fee_account_id = fields.Many2one(
        "account.account",
        string="Factor Fee Account",
        domain="[('internal_type', '=', 'other'), ('internal_group', '=', 'expense'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
    )
    factor_holdback_account_id = fields.Many2one(
        "account.account",
        string="Factor Holdback Account",
        help="Proportional holdback",
        domain="[('internal_type', '=', 'other'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
    )
    factor_limit_holdback_account_id = fields.Many2one(
        "account.account",
        string="Factor Limit Holdback Account",
        help="Holdback when the customer credit is over the limit",
        domain="[('internal_type', '=', 'other'), ('deprecated', '=', False), ('company_id', '=', current_company_id)]",
    )
    factor_tax_id = fields.Many2one(
        "account.tax",
        string="Factor Fee Purchase Tax",
        domain="[('type_tax_use', '=', 'purchase')]",
    )

    # computed fields:
    factor_debit = fields.Monetary(
        string="Factor Debit", compute="_compute_factor_debit_credit"
    )
    factor_credit = fields.Monetary(
        string="Factor Credit", compute="_compute_factor_debit_credit"
    )
    factor_balance = fields.Monetary(
        string="Factor Balance", compute="_compute_factor_debit_credit"
    )
    factor_holdback_balance = fields.Monetary(
        string="Factor Holdback Balance", compute="_compute_factor_debit_credit"
    )
    factor_limit_holdback_balance = fields.Monetary(
        string="Factor Limit Holdback Balance", compute="_compute_factor_debit_credit"
    )
    factor_customer_credit = fields.Monetary(
        string="Factor Customer Credit", compute="_compute_factor_debit_credit"
    )

    def _compute_factor_debit_credit(self):
        self.factor_debit = 0
        self.factor_credit = 0
        self.factor_balance = 0
        if not self.ids:
            return
        account_ids = (
            self.mapped("default_account_id").ids
            + self.mapped("factor_holdback_account_id").ids
            + self.mapped("factor_limit_holdback_account_id").ids
        )
        payment_modes = self.env["account.payment.mode"].search(
            [("fixed_journal_id", "in", self.ids)]
        )

        partner = self._context.get("compute_factor_partner")
        if partner:
            where_extra = """
                AND line.partner_id = %s AND parent_state = 'posted'
            """ % (
                int(partner.id)  # int() is for blocking SQL injection
            )
            account_ids += (partner.property_account_receivable_id.id,)
        else:
            where_extra = "AND parent_state='posted'"

        self.env.cr.execute(
            """
            SELECT line.account_id,
                   SUM(line.balance) AS balance,
                   SUM(line.debit) AS debit,
                   SUM(line.credit) AS credit
            FROM account_move_line AS line
            JOIN account_move AS move
            ON line.move_id = move.id
            WHERE line.account_id IN %s
            AND (move.move_type != 'out_invoice' OR payment_state_with_factor != 'factor_paid')
            AND (move.move_type != 'out_invoice' OR move.payment_mode_id IN %s)
        """
            + where_extra
            + "GROUP BY line.account_id",
            [tuple(account_ids), tuple(payment_modes.ids) or (0,)],
        )
        result = {r["account_id"]: r for r in self.env.cr.dictfetchall()}
        for journal in self:
            res = result.get(journal.default_account_id.id) or {
                "debit": 0,
                "credit": 0,
                "balance": 0,
            }
            journal.factor_debit = res["debit"]
            journal.factor_credit = res["credit"]
            journal.factor_balance = res["balance"]
            if result.get(journal.factor_holdback_account_id.id):
                journal.factor_holdback_balance = result.get(
                    journal.factor_holdback_account_id.id
                )["balance"]
            else:
                journal.factor_holdback_balance = 0
            if result.get(journal.factor_limit_holdback_account_id.id):
                journal.factor_limit_holdback_balance = result.get(
                    journal.factor_limit_holdback_account_id.id
                )["balance"]
            else:
                journal.factor_limit_holdback_balance = 0
            if partner:
                journal.factor_customer_credit = result.get(
                    partner.property_account_receivable_id.id
                )[
                    "debit"
                ]  # debit of customer invoices and != 'factor_paid'
            else:
                journal.factor_customer_credit = 0

    @api.depends("type")
    def _compute_default_account_type(self):
        super()._compute_default_account_type()
        # FIXME usability: you cannot select the factor account before you save
        for journal in self:
            if journal.is_factor:
                journal.default_account_type = self.env.ref(
                    "account.data_account_type_current_liabilities"
                ).id

    def action_open_factor_to_transfer(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_move_out_invoice_type"
        )
        action[
            "domain"
        ] = "[('payment_state_with_factor', '=', 'to_transfer_to_factor')]"
        return action

    def action_open_factor_to_pay(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_move_out_invoice_type"
        )
        action[
            "domain"
        ] = "[('payment_state_with_factor', '=', 'transferred_to_factor')]"
        return action

    def action_open_factor_holdback(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_account_moves_all"
        )
        action[
            "domain"
        ] = "[('full_reconcile_id', '=', False), ('account_id', 'in', %s)]" % (
            (
                self.factor_holdback_account_id.id,
                self.factor_limit_holdback_account_id.id,
            ),
        )
        return action
