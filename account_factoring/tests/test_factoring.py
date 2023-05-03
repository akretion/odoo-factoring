# Copyright (C) 2023 - TODAY Raphaël Valyi - Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestFactorInvoice(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.account_account = cls.env["account.account"]
        cls.account_factor = cls.account_account.create(
            dict(
                code="140000",
                name="FACTOR",
                user_type_id=cls.env.ref(
                    "account.data_account_type_current_liabilities"
                ).id,
                internal_type="other",
                internal_group="liability",
                reconcile=False,
            )
        )
        cls.account_factor_holdback = cls.account_account.create(
            dict(
                code="140010",
                name="FACTOR - holdback",
                user_type_id=cls.env.ref(
                    "account.data_account_type_current_liabilities"
                ).id,
                internal_type="other",
                internal_group="liability",
                reconcile=True,
            )
        )
        cls.account_factor_limit_holdback = cls.account_account.create(
            dict(
                code="140020",
                name="FACTOR - limit holdback",
                user_type_id=cls.env.ref(
                    "account.data_account_type_current_liabilities"
                ).id,
                internal_type="other",
                internal_group="liability",
                reconcile=True,
            )
        )
        cls.journal_factor = cls.env["account.journal"].create(
            {
                "name": "FACTOR",
                "code": "FACT",
                "type": "bank",
                "is_factor": True,
                "default_account_id": cls.account_factor.id,
                "factor_holdback_account_id": cls.account_factor_holdback.id,
                "factor_limit_holdback_account_id": cls.account_factor_limit_holdback.id,
                "factor_holdback_percent": 10,
            }
        )
        cls.payment_mode_factor = cls.env["account.payment.mode"].create(
            {
                "name": "FACT",
                "payment_method_id": cls.env.ref(
                    "account.account_payment_method_manual_in"
                ).id,
                "bank_account_link": "fixed",
                "fixed_journal_id": cls.journal_factor.id,
            }
        )

        cls.factor_inv = cls.init_invoice(
            "out_invoice",
            partner=cls.env.ref("base.res_partner_12"),
            products=[cls.product_a],
        )

        cls.factor_inv.payment_mode_id = cls.payment_mode_factor

    def initial_balance(self):
        self.assertEqual(self.factor_inv.partner_id.factor_credit, 0)
        self.assertEqual(self.factor_inv.partner_id.factor_holdback, 0)

    def test_non_factor_customer_invoice(self):
        """
        Test normal invoices are not impacted by the factor logic
        """
        normal_inv = self.factor_inv.copy({"payment_mode_id": False})
        receivable_lines = normal_inv.line_ids.filtered(
            lambda line: line.account_id.user_type_id.type == "receivable"
        )
        self.assertEqual(
            receivable_lines[0].account_id.id,
            self.company_data["default_account_receivable"].id,
        )
        self.assertEqual(normal_inv.amount_total, 1000.0 * 1.15)
        self.assertEqual(normal_inv.state, "draft")
        normal_inv._post()
        self.assertEqual(normal_inv.state, "posted")
        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=[normal_inv.id]
        ).create(
            {
                "payment_date": normal_inv.date,
            }
        )._create_payments()
        self.assertEqual(normal_inv.payment_state, "paid")
        self.assertEqual(normal_inv.payment_state_with_factor, "paid")

    def test_draft_customer_invoice(self):
        self.assertEqual(self.factor_inv.amount_total, 1000.0 * 1.15)
        receivable_lines = self.factor_inv.line_ids.filtered(
            lambda line: line.account_id.user_type_id.type == "receivable"
        )
        self.assertEqual(
            receivable_lines[0].account_id.id,
            self.company_data["default_account_receivable"].id,
        )
        self.assertEqual(self.factor_inv.state, "draft")
        self.factor_inv._post()
        self.assertEqual(self.factor_inv.state, "posted")
        self.assertEqual(
            self.factor_inv.payment_state_with_factor, "to_transfer_to_factor"
        )

    def test_transfer_to_factor(self):
        self.factor_inv._post()
        self.factor_inv.button_transfer_to_factor()
        self.assertEqual(self.factor_inv.state, "posted")
        self.assertEqual(
            self.factor_inv.payment_state_with_factor, "transferred_to_factor"
        )
        self.assertEqual(self.factor_inv.payment_state, "paid")
        transfer = self.factor_inv.factor_transfer_id
        self.assertTrue(
            abs(transfer.amount_total - 1000.0 * 1.15) < 0.01
        )  # 15% sale VAT
        factor_line = transfer.line_ids.filtered(
            lambda line: line.account_id == self.account_factor
        )
        self.assertTrue(abs(factor_line.debit - 1000 * 1.15 * 0.9) < 0.01)

        factor_holdback_line = transfer.line_ids.filtered(
            lambda line: line.account_id == self.account_factor_holdback
        )
        self.assertTrue(abs(factor_holdback_line.debit - 1000 * 1.15 * 0.1) < 0.01)

        self.assertEqual(self.factor_inv.partner_id.factor_credit, 1000 * 1.15)
        self.assertEqual(self.factor_inv.partner_id.factor_holdback, 0)

    def test_factor_paid(self):
        self.factor_inv._post()
        self.factor_inv.button_transfer_to_factor()
        self.factor_inv.button_factor_paid(is_test=True)
        self.assertEqual(self.factor_inv.state, "posted")
        self.assertEqual(self.factor_inv.payment_state_with_factor, "factor_paid")
        # FIXME the following only work if we enable the commit in button_factor_paid
        # above...
        # self.assertEqual(self.factor_inv.partner_id.factor_credit, 0)
        self.assertEqual(self.factor_inv.partner_id.factor_holdback, 0)

    def test_factor_holdback_limit(self):
        self.factor_inv.partner_id.factor_credit_limit = 800
        self.factor_inv._post()
        self.factor_inv.button_transfer_to_factor()
        transfer = self.factor_inv.factor_transfer_id
        self.assertTrue(
            abs(transfer.amount_total - 1000.0 * 1.15) < 0.01
        )  # 15% sale VAT
        factor_line = transfer.line_ids.filtered(
            lambda line: line.account_id == self.account_factor
        )
        self.assertEqual(factor_line.debit, 800)  # only up to the credit limit
        factor_holdback_line = transfer.line_ids.filtered(
            lambda line: line.account_id == self.account_factor_holdback
        )
        self.assertTrue(abs(factor_holdback_line.debit - 1000 * 1.15 * 0.1) < 0.01)
        factor_limit_holdback_line = transfer.line_ids.filtered(
            lambda line: line.account_id == self.account_factor_limit_holdback
        )
        self.assertEqual(factor_limit_holdback_line.debit, 235)
        self.assertEqual(self.factor_inv.partner_id.factor_credit, 1000 * 1.15)
        self.assertEqual(self.factor_inv.partner_id.factor_holdback, 0)

    def test_cancel_factor(self):
        self.factor_inv._post()
        self.factor_inv.button_transfer_to_factor()
        self.factor_inv.button_cancel_factor()
        self.assertEqual(self.factor_inv.payment_state, "not_paid")

    def test_dashboard(self):
        self.factor_inv._post()
        self.factor_inv.button_transfer_to_factor()
        self.journal_factor.get_factor_line_graph_data()
        self.journal_factor.get_journal_dashboard_datas()
