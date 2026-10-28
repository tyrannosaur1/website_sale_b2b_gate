# -*- coding: utf-8 -*-
"""The quote request record, its window and its notification."""
from datetime import timedelta
from unittest.mock import patch

from odoo import fields

from .common import GateCase


class TestQuoteRequest(GateCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Quote = cls.env["website.quote.request"]

    def _submit(self, email="lead@example.com", **kwargs):
        return self.Quote._b2b_gate_submit(
            self.website, email, template=self.product, **kwargs)

    def test_a_request_stores_the_product_and_the_message(self):
        quote, created = self._submit(message="Twelve pieces, please")
        self.assertTrue(created)
        self.assertEqual(quote.email, "lead@example.com")
        self.assertEqual(quote.message, "Twelve pieces, please")
        self.assertEqual(len(quote.line_ids), 1)
        self.assertEqual(quote.line_ids.product_tmpl_id, self.product)
        self.assertEqual(quote.line_ids.name, "Gated widget")
        self.assertEqual(quote.state, "new")
        self.assertTrue(quote.name.startswith("QR/"), quote.name)

    def test_a_second_submission_in_the_window_is_the_same_request(self):
        first, _created = self._submit()
        second, created = self._submit()
        self.assertFalse(created)
        self.assertEqual(first, second)
        self.assertEqual(self.Quote.search_count([]), 1)

    def test_the_window_ignores_the_case_of_the_address(self):
        first, _created = self._submit("Lead@Example.com")
        second, created = self._submit("lead@example.com")
        self.assertFalse(created)
        self.assertEqual(first, second)

    def test_a_submission_after_the_window_is_a_new_request(self):
        """Negative control for the five minute rule."""
        first, _created = self._submit()
        later = fields.Datetime.now() + timedelta(minutes=6)
        second, created = self._submit(now=later)
        self.assertTrue(created)
        self.assertNotEqual(first, second)
        self.assertEqual(self.Quote.search_count([]), 2)

    def test_two_visitors_produce_two_requests(self):
        self._submit("first@example.com")
        _quote, created = self._submit("second@example.com")
        self.assertTrue(created)
        self.assertEqual(self.Quote.search_count([]), 2)

    def test_the_notification_carries_the_request_to_the_configured_address(self):
        quote, _created = self._submit(message="Please quote 12 units")
        template = self.env.ref("website_sale_b2b_gate.mail_template_quote_request")
        Mail = type(self.env["mail.mail"])
        with patch.object(Mail, "send", lambda mail, **kwargs: True):
            template.send_mail(
                quote.id,
                email_values={"email_to": self.website.b2b_gate_quote_email},
                force_send=True)
        mail = self.env["mail.mail"].search([
            ("model", "=", "website.quote.request"),
            ("res_id", "=", quote.id),
        ])
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.email_to, "quotes@example.com")
        self.assertIn(quote.name, mail.subject)
        self.assertIn("Gated widget", mail.body_html)
        self.assertIn("Please quote 12 units", mail.body_html)

    def test_the_notification_address_falls_back_on_the_company(self):
        self.website.b2b_gate_quote_email = False
        self.assertEqual(self.website._b2b_gate_quote_email_to(), "shop@example.com")
        self.website.company_id.email = False
        self.assertEqual(self.website._b2b_gate_quote_email_to(), "")
