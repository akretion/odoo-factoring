# Copyright (C) 2021 - TODAY Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, api, models
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    # NOTE this could go to OCA/bank-payment/account_payment_mode no?
    @api.depends("company_id", "source_currency_id")
    def _compute_journal_id(self):
        super()._compute_journal_id()
        for wiz in self:
            payment_mode = False
            for line in wiz.line_ids:
                if line.move_id.payment_mode_id:
                    if payment_mode and payment_mode != line.move_id.payment_mode_id:
                        raise UserError(
                            _("You cannot pay different with payment modes together!")
                        )
                    else:
                        payment_mode = line.move_id.payment_mode_id
            if payment_mode and payment_mode.fixed_journal_id:
                wiz.journal_id = payment_mode.fixed_journal_id

    def _create_payments(self):
        self.ensure_one()
        if self.journal_id.is_factor:
            return super(
                AccountPaymentRegister,
                self.with_context(
                    {
                        # context to avoid errors in account.payment#_synchronize_from_moves
                        "skip_account_move_synchronization": True,
                        "factor_move_synchronization": True,
                    }
                ),
            )._create_payments()
        else:
            return super()._create_payments()
