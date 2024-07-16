# © 2024 Open Source Integrators, Daniel Reis
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class Partner(models.Model):
    _inherit = "res.partner"

    factor_journal_id = fields.Many2one(
        comodel_name="account.journal",
        domain="[('factor_type', '!=', False)]",
        help="Select the factoring service for this partner.",
    )

    def _get_factor_ref(self, factor_type):
        "Can be overrided in your factor module if required"
        # TODO propose to upper repository branch
        self.ensure_one()
        return self.ref
