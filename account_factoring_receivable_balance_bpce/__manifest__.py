# © 2022 David BEAL @ Akretion
# © 2022 Alexis DE LATTRE @ Akretion

{
    "name": "Account Factoring Receivable Balance BPCE",
    "version": "16.0.1.0.0",
    "category": "Accounting",
    "license": "AGPL-3",
    "website": "https://github.com/akretion/odoo-factoring",
    "author": "Akretion",
    "maintainers": [
        "bealdav",
        "alexis-via",
    ],
    "depends": [
        "account_factoring_receivable_balance",
        "l10n_fr",
    ],
    "data": [
        "views/partner.xml",
        "views/company.xml",
    ],
    "demo": [
        "views/company_demo.xml",
    ],
    # Recent changes in dependencies have not been evaluate for this module
    "installable": False,
}
