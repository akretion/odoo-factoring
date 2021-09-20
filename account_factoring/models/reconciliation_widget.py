# Copyright (C) 2021 - TODAY Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, api, models
from odoo.osv import expression


class AccountReconciliation(models.AbstractModel):
    _inherit = "account.reconciliation.widget"

    @api.model
    def _domain_move_lines_for_reconciliation(
        self,
        st_line,
        aml_accounts,
        partner_id,
        excluded_ids=None,
        search_str=False,
        mode="rp",
    ):
    	domain = super()._domain_move_lines_for_reconciliation(
	        st_line,
	        aml_accounts,
	        partner_id,
	        excluded_ids=excluded_ids,
	        search_str=search_str,
	        mode=mode,
    	)
    	if mode=="other":
            for journal in self.env['account.journal'].search([
                ("company_id", "=", st_line.company_id.id),
                ("is_factor", "=", True)
            ]):
                domain = expression.AND(
                    [
                        domain,
                        [
                            (
                                "account_id",
                                "!=",
                                journal.factor_holdback_account_id.id,
                                # this account is reconcilable (used when the
                                # factor is paid), but we shouldn't leave it
                                # for selection for bank transfers.
                            )
                        ],
                    ]
                )

            domain = expression.AND(
                [
                    domain,
                    [
                        (
                            "move_id.state",
                            "=",
                            "posted",  # makes manual factor reconciliation much easier
                        )
                    ],
                ]
            )
            return domain