# Copyright 2021 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Account Factoring",
    "summary": """
        Factoring""",
    "version": "14.0.1.0.0",
    "license": "AGPL-3",
    "author": "Akretion,Odoo Community Association (OCA)",
    "depends": [
        "account_payment_partner",
        # "account_reconciliation_widget",
    ],
    "data": [
        "views/account_journal.xml",
        "views/account_journal_dashboard_view.xml",
        "views/account_move.xml",
        "views/res_partner.xml",
    ],
    "demo": [
        "demo/factoring.xml",
    ],
}
