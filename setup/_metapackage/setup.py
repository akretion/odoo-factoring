import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo-addons-akretion-odoo-factoring",
    description="Meta package for akretion-odoo-factoring Odoo addons",
    version=version,
    install_requires=[
        'odoo-addon-account_factoring_receivable_balance>=16.0dev,<16.1dev',
        'odoo-addon-account_factoring_receivable_balance_eurofactor>=16.0dev,<16.1dev',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 16.0',
    ]
)
