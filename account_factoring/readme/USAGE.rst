Create a new Journal
====================

Example in France for FactoFrance:

1. create a new account journal of type Bank with the Is Factor checkbox checked.
2. Define a code like FACTO. Save (yes you should save before filling the next information).
3. Bank Account: 467000
4. In the Factoring tab: factor fee 0.03%
5. Factor Fee Account: 622500
6. Factor Fee Purchase Tax: 20%
7. Factor Holdback Account: create a new chart account 467010 like 467000, but mark it a reconciable.
8. Factor Holdback %: 10%
9. Factor Limit Holdback Account: create a new chart account 467020 like 467000, but mark it a reconciable.



Create a factor payment mode
============================

Create a new inbound payment mode with a fixed bank journal
and associate the factor journal to it.
You can set this payment mode as default for a customer in the Sale & Purchase tab of the customer.


Invoicing
=========

Create a customer invoice, set the payment mode as factor (if not coming from the customer settings already) and confirm the invoice.
The confirmed invoice account.move is exactly the same as a normal invoice so far.

Now a new button "Transfer to Factor" is available in place of the pay invoice button. You can use it to transfer the customer credit
to the factor.

When you transfer the invoice to the factor, a new account.move is created and reconciled with the receivable from the invoice account.move.
A percentual amount is hold back. And if the customer credit limit with the factor is over a specific limit, a limit holdback applies (TODO detail).

You can take the money from the factor to your bank account with a normal bank statement that you will reconcile
with the amounts made available to you by the factor.

When you click on the "Factor Paid" button, the hold back amounts are given back to the factor account.


Bank statements
===============


You should use standard bank statements to register the money transfer from the factor account to your bank account.
Define a reconciliation model for creating a counterpart of 100% of your bank statement line in your factor account
and use it every time you need to reconcile a factor transfer in your bank statement.


Note on reconciliations
=======================

Money made available can be related to several invoices and holdback releases and if you fail to simulate the factor
behavior exactly, chances are you'll have small diference between the amount available in Odoo and at your factor.
That's why we assume not using reconciliation for the money transfered from the factor to the bank.

On the other hand, we reconcile the holdback and holdback releases in order to keep the holdback history clean
and easy to inspect. Now these reconciliations can have more than 2 account.move.lines.

Hence even if we don't simulate exactly the holdback money, once the customer paid everything to the factor the
holdback amounts are reconciled and errors don't accumulate.


Note on factor API
==================

This module is factor agnostic (but tested in France with FactoFrance). It tries to simulate what the factor does
but it doesn't integrate with any factor API. This could be done in extension modules to:

* automate the invoice transfer to the factor
* mark invoices paid to the factor automatically
* provide the exact amount available and holdback amounts.


Note on tests
=============

Akretion had only 1 customer for this initial development and tests are not easy because of all the set up and
because it depends on a specific chart of accounts. So so far this module was tested manually with this scenario
https://docs.google.com/spreadsheets/d/1bxi1J3XgExy2fX74ixjn52dX1xx1cqH6X-WEhyeXarU/edit?usp=sharing
were taxes and fees were neglected on purpose.
