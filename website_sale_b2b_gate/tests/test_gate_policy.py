# -*- coding: utf-8 -*-
"""Who sees a price: the visitor, the customer, the allowed group."""
from .common import GateCase


class TestGatePolicy(GateCase):

    # -- negative control ---------------------------------------------
    def test_gate_off_shows_every_price(self):
        """The whole module must be inert when the switch is off."""
        self.gate_off()
        product = self.as_public(self.product)
        self.assertFalse(product._b2b_gate_hides_price())
        self.assertFalse(product._b2b_gate_blocks_cart())
        self.assertFalse(self.as_public(self.website)._b2b_gate_hides_prices())

    # -- who is gated --------------------------------------------------
    def test_public_visitor_gets_no_price_and_no_cart(self):
        product = self.as_public(self.product)
        self.assertTrue(product._b2b_gate_hides_price())
        self.assertTrue(product._b2b_gate_blocks_cart())

    def test_internal_user_keeps_prices(self):
        """Staff must be able to check the site they configured."""
        product = self.as_internal(self.product)
        self.assertFalse(product._b2b_gate_hides_price())
        self.assertFalse(product._b2b_gate_blocks_cart())

    def test_portal_customer_outside_the_groups_is_gated(self):
        self.assertTrue(self.as_portal(self.product)._b2b_gate_hides_price())

    def test_member_of_an_allowed_group_sees_prices(self):
        self.website.b2b_gate_allowed_group_ids = [(6, 0, [self.allowed_group.id])]
        product = self.as_allowed(self.product)
        self.assertFalse(product._b2b_gate_hides_price())
        self.assertFalse(product._b2b_gate_blocks_cart())
        # ... and the group does not open the gate for anyone else
        self.assertTrue(self.as_portal(self.product)._b2b_gate_hides_price())

    def test_prices_mode_leaves_the_cart_open(self):
        self.website.b2b_gate_mode = "prices"
        product = self.as_public(self.product)
        self.assertTrue(product._b2b_gate_hides_price())
        self.assertFalse(product._b2b_gate_blocks_cart())

    def test_whole_shop_only_walls_anonymous_visitors(self):
        self.website.b2b_gate_mode = "whole_shop"
        self.assertTrue(self.as_public(self.website)._b2b_gate_requires_login())
        self.assertFalse(self.as_portal(self.website)._b2b_gate_requires_login())
        # a signed-in customer gets the ordinary shop, prices included
        self.assertFalse(self.as_portal(self.product)._b2b_gate_hides_price())

    # -- category inheritance -----------------------------------------
    def test_a_parent_category_policy_reaches_its_children(self):
        parent = self.env["product.public.category"].create({
            "name": "Gate parent", "b2b_gate_policy": "hidden"})
        child = self.env["product.public.category"].create({
            "name": "Gate child", "parent_id": parent.id})
        self.product.public_categ_ids = [(6, 0, [child.id])]
        self.assertTrue(self.as_public(self.product)._b2b_gate_hides_price())

    def test_product_visible_overrides_a_hidden_category(self):
        self.product.b2b_gate_policy = "visible"
        self.category.b2b_gate_policy = "hidden"
        self.assertFalse(self.as_public(self.product)._b2b_gate_hides_price())

    def test_the_strictest_category_wins(self):
        other = self.env["product.public.category"].create({
            "name": "Gate hidden", "b2b_gate_policy": "hidden"})
        self.category.b2b_gate_policy = "visible"
        self.product.public_categ_ids = [(6, 0, [self.category.id, other.id])]
        self.assertTrue(self.as_public(self.product)._b2b_gate_hides_price())

    def test_a_product_policy_does_nothing_without_the_gate(self):
        """A stray "always hide" is not a price policy of its own."""
        self.product.b2b_gate_policy = "hidden"
        self.gate_off()
        self.assertFalse(self.as_public(self.product)._b2b_gate_hides_price())

    def test_the_open_product_keeps_its_price_in_the_same_shop(self):
        self.assertTrue(self.as_public(self.product)._b2b_gate_hides_price())
        self.assertFalse(self.as_public(self.open_product)._b2b_gate_hides_price())

    # -- price surfaces outside this module ---------------------------
    def test_a_price_surface_gets_no_price_through_the_hook(self):
        """A caller that prints its own price gets ``None``, not a figure."""
        suggestion_price = self.as_public(self.product)._b2b_gate_public_price(
            100.0)
        detail = "" if suggestion_price is None else "%.2f" % suggestion_price
        self.assertIsNone(suggestion_price)
        self.assertEqual(detail, "")
        # the same caller on a product the gate leaves alone, and with the
        # gate switched off, still gets the number it computed
        self.assertEqual(
            self.as_public(self.open_product)._b2b_gate_public_price(250.0),
            250.0)
        self.gate_off()
        self.assertEqual(
            self.as_public(self.product)._b2b_gate_public_price(100.0), 100.0)
