# © 2022 David BEAL @ Akretion
# © 2022 Alexis DE LATTRE @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

from odoo import exceptions, fields, models

logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    factor_type = fields.Selection(string="Factor", selection=[], tracking=True)
    factor_code = fields.Char(help="Account Number for factor company")
    factor_start_date = fields.Date(
        tracking=True,
        help="No account move will be selected before this date",
    )
    factor_invoice_journal_ids = fields.Many2many(
        string="Limit Factoring to Journals",
        comodel_name="account.journal",
        relation="account_journal_factor_invoice_rel",
        column1="factor_journal_id",
        column2="sale_journal_id",
        tracking=True,
        help="Journals to limit Factoring to. Leave blank to allow all journals",
    )
    factoring_receivable_account_id = fields.Many2one(
        comodel_name="account.account", string="Receivable Account", tracking=True
    )
    factoring_current_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Current Account",
        tracking=True,
    )
    factoring_holdback_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Holdback Account",
        tracking=True,
    )
    factoring_pending_recharging_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Pending Recharging Account",
        tracking=True,
    )
    factoring_expense_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Expense Account",
        tracking=True,
    )

    _sql_constraints = [
        (
            "currency_factor_curr_type_cpny_unique",
            "UNIQUE(currency_id, factor_type, type, company_id)",
            "Field Factor type must be unique by Currency, Journal type, and Company",
        )
    ]

    def _get_domain_for_factor(self):
        self.ensure_one()
        self = self.with_company(self.company_id.id)
        domain = []
        if self.factor_start_date:
            domain.append(("date", ">=", self.factor_start_date))
        if self.factor_invoice_journal_ids:
            domain.append(("journal_id", "in", self.factor_invoice_journal_ids.ids))
        else:
            raise exceptions.UserError(
                "Merci de définir les journaux sur lequels repose le factor "
                f"sur le journal {self.display_name}"
            )
        return domain
