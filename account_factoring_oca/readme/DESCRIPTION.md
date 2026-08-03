## accountfactoring

Accounts Receivable Factoring for Odoo. This module is in incubation
before targeting an OCA inclusion.

This is the **OCA variant** adapted for
`OCA/bank-payment-alternative <https://github.com/OCA/bank-payment-alternative>`_.
It depends on `account_payment_base_oca` and uses native Odoo 18
`account.payment.method.line` (field `preferred_payment_method_line_id`)
instead of `account.payment.mode` and `payment_mode_id` from the
original `account_factoring` module (which depends on
`OCA/bank-payment <https://github.com/OCA/bank-payment>`_).
