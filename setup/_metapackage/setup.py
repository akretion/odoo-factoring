import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo14-addons-akretion-odoo-factoring",
    description="Meta package for akretion-odoo-factoring Odoo addons",
    version=version,
    install_requires=[
        'odoo14-addon-account_factoring',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 14.0',
    ]
)
