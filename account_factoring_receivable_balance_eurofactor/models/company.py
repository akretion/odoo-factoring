# © 2022 David BEAL @ Akretion
# © 2022 Alexis DE LATTRE @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""
Pour ce factor un seul journal de facto de type OD est nécessaire
pour l'envoi des credits : facture et avoir
"""

import logging

from odoo import _, fields, models
from odoo.exceptions import RedirectWarning, UserError
from odoo.tests import Form

logger = logging.getLogger(__name__)


FACTO_TYPE = "eurof"


class ResCompany(models.Model):
    _inherit = "res.company"

    def _prepare_data_for_factor(self, move_type="out_invoice"):
        self.ensure_one()
        move_form = Form(
            self.env["account.move"]
            .with_company(self.env.company)
            .with_context(
                default_move_type=move_type,
                account_predictive_bills_disable_prediction=True,
            )
        )
        move_form.invoice_date = fields.Date.from_string("2025-10-03")
        move_form.date = move_form.invoice_date
        move_form.partner_id = self.env.ref("base.res_partner_2")

    def ui_populate_data_for_factor(self):
        raise UserError(_("Not yet implemented"))
        # self._prepare_data_for_factor()

    def ui_configure_eurof_factoring_balance(self):
        self.ensure_one()
        self._configure_eurof_factoring()
        eurof_journals = self.env["account.journal"].search(
            [("factor_type", "=", FACTO_TYPE), ("company_id", "=", self.id)]
        )
        action_id = self.env.ref("account.action_account_journal_form").id
        active_ids = ",".join([str(x) for x in eurof_journals.ids])

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Configuration réussie",
                "type": "success",  # warning/success
                "message": "Consulter les journaux et comptes configurés",
                "links": [
                    {
                        "label": "Voir les journaux",
                        "url": f"#action={action_id}&model=account.journal"
                        f"&active_ids={active_ids}",
                    }
                ],
                "sticky": True,  # True/False will display for few seconds if false
                "next": action_id,
            },
        }

    def _configure_eurof_factoring(self):
        """Mainly copied from l10n_fr_account_vat_return
        The code is created here and not in the test,
        because it can be very useful for demos too

        This method can be called to configure actual company or a new one
        """
        self = self.sudo()
        self.ensure_one()
        currency = self.env.ref(
            f"base.{self.currency_id.name.upper()}", raise_if_not_found=False
        )
        if not currency:
            # pylint: disable=C8107
            raise UserError(f"La devise '{currency.name}' est inconnue")
        if self.env["account.journal"].search(
            [
                ("factor_type", "=", FACTO_TYPE),
                ("company_id", "=", self.id),
                ("currency_id", "=", currency.id),
            ]
        ):
            # pylint: disable=C8107
            raise UserError(
                f"Un journal Eurofactor avec la devise '{currency.name}'"
                " existe déjà. Configuration annulée"
            )
        fr_chart_template = self.env.ref("l10n_fr.l10n_fr_pcg_chart_template")
        company = self
        if self.chart_template_id != fr_chart_template:
            action = self.env.ref("account.action_account_config").read()[0]
            action["name"] = f"Configure accounting chart in '{self.name}' company"
            raise RedirectWarning(
                _(
                    "The accounting chart installed in this company "
                    "is not the french one. Install it first"
                ),
                action,
                _("Go to accounting chart configuration"),
                {"active_ids": [self.env.company.id]},
            )
        if self.env["account.journal"].search(
            [
                ("factor_type", "=", FACTO_TYPE),
                ("currency_id", "=", currency.id),
                ("company_id", "=", company.id),
            ]
        ):
            raise UserError(
                _(
                    f"Eurofactor Journal with currency '{currency.name}' already exist."
                    " Configuration aborted"
                )
            )
        vals = {"reconcile": False, "tax_ids": False, "company_id": company.id}
        acc = {}
        suffix = self._get_factor_shortname()
        for acco in (
            ["4115", "Factoring Receivable", "income"],
            ["4671", "Factoring Current", "income"],
            ["4672", "Factoring Holdback", "income"],
            ["4673", "Factoring Recharging", "income"],
        ):
            code = f"{acco[0]}{suffix}"
            values = {"code": code, "name": acco[1], "account_type": acco[2]}
            values.update(vals)
            acc[code] = self.env["account.account"].create(values)
        expense_acc = self.env["account.account"].search(
            [("code", "=", "622500"), ("company_id", "=", company.id)]
        )
        self.env["account.journal"].create(
            {
                "name": f"Eurofactor Cr.Ag. {currency.symbol}",
                "type": "general",
                "factor_type": FACTO_TYPE,
                "code": FACTO_TYPE.upper(),
                "factor_data": self._populate_eurof_settings(),
                "company_id": company.id,
                "factoring_receivable_account_id": acc[f"4115{suffix}"].id,
                "factoring_current_account_id": acc[f"4671{suffix}"].id,
                "factoring_holdback_account_id": acc[f"4672{suffix}"].id,
                "factoring_pending_recharging_account_id": acc[f"4673{suffix}"].id,
                "factoring_expense_account_id": expense_acc.id,
            }
        )
        return company

    def _populate_eurof_settings(self):
        return "client = 45678\nemetteurD = 54321\nemetteurE = 12345\nmail_prod = \n"

    def _get_factor_shortname(self):
        """Allow to customze account name
        CA : Crédit agricole
        can be LCL for Le Crédit Lyonnais
        """
        return "CA"
