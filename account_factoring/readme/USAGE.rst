Create a new Journal
====================

Example in France fro FactoFrance:

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
The only difference is that you will reconcile factor bank statement lines not with a payable or a receivable but with
using the miscellaneous tab instead. You should 1st match against the factor account.

But in the case where the amount holded back by the factor is inferior to what was expected,
then you can select the appropriate lines from the limit holdback account for reconciliation.


