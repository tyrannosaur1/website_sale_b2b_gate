# -*- coding: utf-8 -*-
"""The rendered pages: what a visitor actually receives."""
import json
import re
from unittest.mock import patch

from odoo.tests.common import HttpCase, tagged

from .common import VARIANT_NEEDS_PRICELIST, VARIANT_ROUTE, GateCase

CSRF_RE = re.compile(r'name="csrf_token"[^>]*value="([^"]+)"')


@tagged("post_install", "-at_install")
class TestGateHttp(GateCase, HttpCase):
    """Every test here speaks to the server the way a browser does."""

    # -- helpers -------------------------------------------------------
    def _get(self, url, **kwargs):
        return self.url_open(url, **kwargs)

    def _csrf(self, url="/b2b/quote"):
        page = self._get(url)
        self.assertEqual(page.status_code, 200)
        found = CSRF_RE.search(page.text)
        self.assertTrue(found, "the page carries no csrf token")
        return found.group(1)

    def _jsonrpc(self, url, params):
        payload = {"jsonrpc": "2.0", "method": "call", "params": params, "id": 1}
        return self.url_open(
            url, data=json.dumps(payload),
            headers={"Content-Type": "application/json"})

    @property
    def product_url(self):
        return self.product.website_url

    # -- product page --------------------------------------------------
    def test_a_visitor_gets_no_price_and_a_quote_button(self):
        page = self._get(self.product_url)
        self.assertEqual(page.status_code, 200)
        self.assertNotRegex(page.text, r"100[.,]00")
        self.assertIn("Prices on request", page.text)
        self.assertIn('id="b2b_gate_block"', page.text)
        self.assertIn('id="b2b_gate_quote_link"', page.text)
        # the buy button is gone and so is the price microdata
        self.assertNotIn('id="add_to_cart"', page.text)
        self.assertNotIn('name="add_to_cart"', page.text)
        self.assertNotIn('itemprop="price"', page.text)

    def test_the_page_is_still_reachable_by_its_direct_url(self):
        """Only the price is hidden, not the page."""
        page = self._get(self.product_url)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Gated widget", page.text)

    def test_staff_still_see_the_price_on_the_page(self):
        admin = self.env.ref("base.user_admin")
        admin.write({"password": "gate_admin_pw"})
        self.authenticate("admin", "gate_admin_pw")
        page = self._get(self.product_url)
        self.assertRegex(page.text, r"100[.,]00")

    def test_the_page_shows_the_price_when_the_gate_is_off(self):
        """Negative control on the same URL."""
        self.gate_off()
        page = self._get(self.product_url)
        self.assertRegex(page.text, r"100[.,]00")
        self.assertNotIn('id="b2b_gate_block"', page.text)

    # -- the shop list -------------------------------------------------
    def test_the_tile_says_price_on_request(self):
        page = self._get("/shop")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Gated widget", page.text)
        self.assertIn("Price on request", page.text)
        self.assertNotRegex(page.text, r"100[.,]00")

    def test_the_tile_shows_its_price_when_the_gate_is_off(self):
        self.gate_off()
        page = self._get("/shop")
        self.assertRegex(page.text, r"100[.,]00")
        self.assertNotIn("Price on request", page.text)

    # -- price filtering ----------------------------------------------
    def test_the_min_price_filter_has_no_effect_for_a_visitor(self):
        page = self._get("/shop?min_price=200")
        self.assertEqual(page.status_code, 200)
        # 100 < 200: a working filter would drop this product
        self.assertIn("Gated widget", page.text)
        self.assertNotIn("o_wsale_price_range_option", page.text)

    def test_the_min_price_filter_works_when_the_gate_is_off(self):
        self.gate_off()
        page = self._get("/shop?min_price=200")
        self.assertNotIn("Gated widget", page.text)
        self.assertIn("o_wsale_price_range_option", page.text)

    # -- the variant route --------------------------------------------
    def test_the_variant_route_answers_without_a_price(self):
        params = {
            "product_template_id": self.product.id,
            "product_id": self.product.product_variant_id.id,
            "combination": [],
            "add_qty": 1,
        }
        if VARIANT_NEEDS_PRICELIST:
            params["pricelist_id"] = self.website.pricelist_id.id
        payload = self._jsonrpc(VARIANT_ROUTE, params).json()
        self.assertNotIn("error", payload, payload)
        self.assertEqual(payload["result"]["price"], 0.0)

    # -- whole shop ----------------------------------------------------
    def test_whole_shop_sends_a_visitor_to_the_login_screen(self):
        self.website.b2b_gate_mode = "whole_shop"
        response = self._get("/shop", allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("/web/login", response.headers.get("Location", ""))
        # the cart is behind the same wall: no whitelist
        cart = self._get("/shop/cart", allow_redirects=False)
        self.assertEqual(cart.status_code, 303)

    def test_a_signed_in_customer_walks_the_whole_shop(self):
        self.website.b2b_gate_mode = "whole_shop"
        admin = self.env.ref("base.user_admin")
        admin.write({"password": "gate_admin_pw"})
        self.authenticate("admin", "gate_admin_pw")
        page = self._get("/shop")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Gated widget", page.text)

    def test_whole_shop_is_inert_for_an_anonymous_visitor_when_disabled(self):
        self.website.b2b_gate_mode = "whole_shop"
        self.gate_off()
        self.assertEqual(self._get("/shop").status_code, 200)

    # -- quote form ----------------------------------------------------
    def test_the_quote_form_creates_a_request_and_one_mail(self):
        page = self._get("/b2b/quote?template_id=%s" % self.product.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Gated widget", page.text)
        token = self._csrf("/b2b/quote?template_id=%s" % self.product.id)

        Mail = type(self.env["mail.mail"])
        with patch.object(Mail, "send", lambda mail, **kwargs: True):
            first = self.url_open("/b2b/quote/submit", data={
                "csrf_token": token,
                "email": "web@example.com",
                "phone": "+33123456789",
                "message": "Twelve pieces please",
                "template_id": self.product.id,
                "quantity": 12,
            })
            self.assertEqual(first.status_code, 200)
            self.assertTrue(first.url.endswith("/b2b/quote/thanks"), first.url)

            second = self.url_open("/b2b/quote/submit", data={
                "csrf_token": token,
                "email": "web@example.com",
                "template_id": self.product.id,
                "quantity": 12,
            })
            self.assertEqual(second.status_code, 200)

        quotes = self.env["website.quote.request"].search(
            [("email", "=", "web@example.com")])
        self.assertEqual(len(quotes), 1, "a double click made two requests")
        self.assertEqual(len(quotes.line_ids), 1)
        self.assertEqual(quotes.line_ids.product_tmpl_id, self.product)
        self.assertEqual(quotes.line_ids.quantity, 12.0)
        mails = self.env["mail.mail"].search([
            ("model", "=", "website.quote.request"), ("res_id", "=", quotes.id)])
        self.assertEqual(len(mails), 1, "a double click sent two mails")

    def test_an_invalid_address_is_refused_without_a_record(self):
        token = self._csrf("/b2b/quote")
        response = self.url_open("/b2b/quote/submit", data={
            "csrf_token": token, "email": "not-an-address", "message": "Hi"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("valid email", response.text)
        self.assertEqual(self.env["website.quote.request"].search_count([]), 0)

    # -- cart ----------------------------------------------------------
    def test_a_gated_product_cannot_enter_the_cart(self):
        payload = self._jsonrpc("/shop/cart/add", {
            "product_template_id": self.product.id,
            "product_id": self.product.product_variant_id.id,
            "quantity": 1,
        }).json()
        self.assertIn("error", payload, "the cart accepted a gated product")
        self.assertEqual(self.env["sale.order.line"].search_count(
            [("product_id", "=", self.product.product_variant_id.id)]), 0)

    def test_a_cart_that_the_gate_closed_cannot_be_paid(self):
        # the line predates the gate: add it while the shop is open ...
        self.gate_off()
        added = self._jsonrpc("/shop/cart/add", {
            "product_template_id": self.product.id,
            "product_id": self.product.product_variant_id.id,
            "quantity": 1,
        })
        self.assertNotIn("error", added.json(), added.json())
        self.assertEqual(added.status_code, 200)
        self.assertEqual(self.env["sale.order.line"].search_count(
            [("product_id", "=", self.product.product_variant_id.id)]), 1)
        # ... then the merchant closes it
        self.website.b2b_gate_enabled = True
        self.website.b2b_gate_mode = "prices_and_cart"
        blocked = self._get("/shop/checkout", allow_redirects=False)
        self.assertEqual(blocked.status_code, 303)
        self.assertIn("/shop/cart", blocked.headers.get("Location", ""))
        self.assertIn("b2b_gate=checkout_blocked", blocked.headers.get("Location", ""))

    # -- structured data ----------------------------------------------
    # From 19 the price also leaves the page as a JSON-LD block, which search
    # engines read long after the visit. Hiding the price block alone left it
    # there, in a machine-readable form, for every crawler.
    def test_the_json_ld_carries_no_offer(self):
        page = self._get(self.product_url)
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('"offers"', page.text)
        self.assertNotIn('"priceCurrency"', page.text)

    def test_the_json_ld_offer_is_back_when_the_gate_is_off(self):
        self.gate_off()
        page = self._get(self.product_url)
        self.assertIn('"offers"', page.text)


    # -- order routes --------------------------------------------------
    # ``/shop/checkout`` is not the only door into payment: the shop also
    # exposes the confirmation and payment steps as URLs of their own.
    def _add_to_cart(self, product=None):
        product = product or self.product
        return self._jsonrpc("/shop/cart/add", {
            "product_template_id": product.id,
            "product_id": product.product_variant_id.id,
            "quantity": 1,
        })

    def _gated_cart(self):
        """A cart that holds a gated line, built while the shop was open."""
        self.authenticate(None, None)
        self.gate_off()
        self._add_to_cart()
        self.website.write({
            "b2b_gate_enabled": True,
            "b2b_gate_mode": "prices_and_cart",
        })
        order = self.env["sale.order"].search(
            [("order_line.product_id", "=", self.product.product_variant_id.id)],
            limit=1)
        self.assertTrue(order, "the cart line was not created")
        return order

    def test_confirm_order_is_not_a_route_on_this_series(self):
        """19 removed the confirmation step; there is nothing to guard."""
        response = self._get("/shop/confirm_order", allow_redirects=False)
        self.assertEqual(response.status_code, 404)

    def test_the_payment_page_refuses_a_gated_cart(self):
        self._gated_cart()
        response = self._get("/shop/payment", allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("b2b_gate=payment_blocked",
                      response.headers.get("Location", ""))

    def test_payment_validation_cannot_confirm_a_gated_cart(self):
        order = self._gated_cart()
        order.order_line.write({"price_unit": 0.0})
        order.invalidate_recordset()
        self.assertEqual(order.amount_total, 0.0)
        self.update_session(sale_order_id=order.id, sale_last_order_id=order.id)
        response = self._get("/shop/payment/validate", allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("b2b_gate=payment_blocked",
                      response.headers.get("Location", ""))
        order.invalidate_recordset()
        self.assertNotEqual(order.state, "sale")

    def test_the_cart_explains_why_it_was_sent_back(self):
        self._gated_cart()
        page = self._get("/shop/cart?b2b_gate=order_blocked")
        self.assertEqual(page.status_code, 200)
        self.assertIn('id="b2b_gate_cart_notice"', page.text)
        self.assertIn("Remove it to continue", page.text)

    def test_an_open_cart_is_not_refused(self):
        """Negative control: the guard is about the product, not the URL."""
        self.gate_off()
        self._add_to_cart(self.open_product)
        response = self._get("/shop/payment", allow_redirects=False)
        self.assertNotIn("b2b_gate",
                         response.headers.get("Location", ""))
