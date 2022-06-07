# Copyright (C) 2021 - TODAY Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import json
import random
from babel.dates import format_date
from datetime import datetime, timedelta
from odoo import api, fields, models
from odoo.release import version
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools.misc import formatLang, format_date as odoo_format_date, get_lang


class AccountJournal(models.Model):
    _inherit = "account.journal"

    # settings fields:
    is_factor = fields.Boolean()
    # Automatic validation if for ease of use with no legal accounting
    # While manual validation is for checking and possibly correcting
    # the Factor transfer move once you have the Factor answer.
    factor_validation = fields.Selection(
        [("automatic", "Automatic"), ("manual", "Manual")],
        default="automatic",
    )
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
        self.factor_holdback_balance = 0
        self.factor_limit_holdback_balance = 0
        if not self.ids:
            return
        account_ids = (
            self.mapped("default_account_id").ids
            + self.mapped("factor_holdback_account_id").ids
            + self.mapped("factor_limit_holdback_account_id").ids
        )
        if not account_ids:
            return
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
            if (
                partner
                and result.get(partner.property_account_receivable_id.id)
            ):
                journal.factor_customer_credit = result.get(
                    partner.property_account_receivable_id.id,
                )["debit"]
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

# ================ Dashboards

    def _kanban_dashboard_graph(self):
        super()._kanban_dashboard_graph()
        for journal in self:
            if journal.is_factor:
                journal.kanban_dashboard_graph = json.dumps(journal.get_factor_line_graph_data())

    def get_factor_line_graph_data(self):
        """
        Quite similar to the original account module get_factor_line_graph_data
        but adapted for factor journals. Override wasn't really possible.
        """
        currency = self.currency_id or self.company_id.currency_id

        def build_graph_data(date, amount):
            #display date in locale format
            name = format_date(date, 'd LLLL Y', locale=locale)
            short_name = format_date(date, 'd MMM', locale=locale)
            return {'x':short_name,'y': amount, 'name':name}

        self.ensure_one()
        BankStatement = self.env['account.bank.statement']
        data = []
        today = datetime.today()
        last_month = today + timedelta(days=-30)
        locale = get_lang(self.env).code

        #starting point of the graph is the last statement
        last_stmt = self._get_last_bank_statement(domain=[('move_id.state', '=', 'posted')])

        last_balance = last_stmt and last_stmt.balance_end_real or 0
        #then we subtract the total amount of bank statement lines per day to get the previous points
        #(graph is drawn backward)
        date = today
        amount = self.factor_balance
        data.append(build_graph_data(today, amount))
        account_ids = (
            self.mapped("default_account_id").ids
#                + self.mapped("factor_holdback_account_id").ids
#                + self.mapped("factor_limit_holdback_account_id").ids
        )
        payment_modes = self.env['account.payment.mode'].search(
            [('fixed_journal_id', 'in', self.ids)]
        )

        query = '''
            SELECT move.date, sum(line.balance) as amount
            FROM account_move_line line
            JOIN account_move move ON line.move_id = move.id
            WHERE move.journal_id = %s
        AND line.account_id IN %s
        AND (move.move_type != 'out_invoice' OR payment_state_with_factor != 'factor_paid')
        AND (move.move_type != 'out_invoice' OR move.payment_mode_id IN %s)
            AND move.date > %s
            AND move.date <= %s
            AND line.parent_state='posted'
            GROUP BY move.date
            ORDER BY move.date desc
        '''
        self.env.cr.execute(query, (self.id, tuple(account_ids), tuple(payment_modes.ids) or (0,), last_month, today))
        query_result = self.env.cr.dictfetchall()
        for val in query_result:
            date = val['date']
            if date != today.strftime(DF):  # make sure the last point in the graph is today
                data[:0] = [build_graph_data(date, amount)]
            amount = currency.round(val['amount'])

        # make sure the graph starts 1 month ago
        if date.strftime(DF) != last_month.strftime(DF):
            data[:0] = [build_graph_data(last_month, amount)]

        [graph_title, graph_key] = self._graph_title_and_key()
        color = '#875A7B' if 'e' in version else '#7c7bad'

        is_sample_data = not last_stmt and len(query_result) == 0
        if is_sample_data:
            data = []
            for i in range(30, 0, -5):
                current_date = today + timedelta(days=-i)
                data.append(build_graph_data(current_date, random.randint(-5, 15)))

        return [{'values': data, 'title': graph_title, 'key': graph_key, 'area': True, 'color': color, 'is_sample_data': is_sample_data}]

    def get_journal_dashboard_datas(self):
        res = super().get_journal_dashboard_datas()
        currency = self.currency_id or self.company_id.currency_id
        if self.is_factor:
            to_transfer = self.env['account.move'].search([('payment_state_with_factor', '=', 'to_transfer_to_factor')])
            number_to_transfer = len(to_transfer)
            sum_to_transfer = sum(to_transfer.mapped('amount_total'))
            waiting_payment = self.env['account.move'].search([('payment_state_with_factor', '=', 'transferred_to_factor')])
            number_waiting_payment = len(waiting_payment)
            sum_waiting_payment = sum(waiting_payment.mapped('amount_total'))
            total_holdback = self.factor_holdback_balance + self.factor_limit_holdback_balance
        else:
            number_to_transfer = 0
            sum_to_transfer = 0
            number_waiting_payment = 0
            sum_waiting_payment = 0
            total_holdback = 0
        res.update({
            'is_factor': self.is_factor,
            'total_holdback': formatLang(self.env, currency.round(total_holdback) + 0.0, currency_obj=currency),
            'number_to_transfer': number_to_transfer,
            'sum_to_transfer': formatLang(self.env, currency.round(sum_to_transfer) + 0.0, currency_obj=currency),
            'number_waiting_payment': number_waiting_payment,
            'sum_waiting_payment': formatLang(self.env, currency.round(sum_waiting_payment) + 0.0, currency_obj=currency),
        })
        return res
