# Copyright 2021 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Account Factoring OCA",
    "summary": """
        Factoring (adapted for OCA/bank-payment-alternative)""",
    "version": "18.0.1.2.0",
    "license": "AGPL-3",
    "author": "Akretion",
    "website": "https://github.com/stephansainleger/odoo-factoring",
    "depends": ["account_payment_base_oca", "account_payment_base_oca_sale"],
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
