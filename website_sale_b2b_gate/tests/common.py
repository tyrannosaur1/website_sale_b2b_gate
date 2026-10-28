# -*- coding: utf-8 -*-
"""Fixtures shared by the gate tests."""
import re

from odoo.tests.common import TransactionCase

PRICE_RE = re.compile(r"100[.,]00")

#: Route the variant selector calls when an attribute changes. It answers
#: with the same dictionary the product page renders, price included.
VARIANT_ROUTE = "/sale/get_combination_info_website"
#: 16 reads the pricelist from the request body of that route.
VARIANT_NEEDS_PRICELIST = True


class GateCase(TransactionCase):
    """A shop with one gated product, one open product and one category."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env["website"].search([], limit=1) \
            or cls.env.company.website_id
        cls.website.write({
            "b2b_gate_enabled": True,
            "b2b_gate_mode": "prices_and_cart",
            "b2b_gate_quote_email": "quotes@example.com",
            "b2b_gate_message": "<p>Prices on request.</p>",
        })
        cls.website.company_id.email = "shop@example.com"

        # The price facet is switched off by default from 20 on; the tests
        # need it on so "the gate hides it" is a statement about the gate.
        # installed inactive: a plain search would not even see it
        filter_view = cls.env["ir.ui.view"].with_context(
            active_test=False).search(
            [("key", "=", "website_sale.filter_products_price")], limit=1)
        if filter_view and not filter_view.active:
            filter_view.active = True

        cls.category = cls.env["product.public.category"].create({
            "name": "Wholesale gate",
        })
        cls.product = cls.env["product.template"].create({
            "name": "Gated widget",
            "list_price": 100.0,
            "sale_ok": True,
            "is_published": True,
            "public_categ_ids": [(6, 0, [cls.category.id])],
        })
        cls.open_product = cls.env["product.template"].create({
            "name": "Public widget",
            "list_price": 250.0,
            "sale_ok": True,
            "is_published": True,
            "b2b_gate_policy": "visible",
        })

        cls.public_user = cls.env.ref("base.public_user")
        cls.portal_user = cls._make_user("gate_portal", ["base.group_portal"])
        # No category: 20 dropped res.groups.category_id, and a group without
        # one is a group all the same.
        cls.allowed_group = cls.env["res.groups"].create({
            "name": "Gate B2B customers",
        })
        cls.allowed_user = cls._make_user("gate_allowed", ["base.group_portal"])
        group_field = (
            "group_ids" if "group_ids" in cls.allowed_user._fields else "groups_id")
        cls.allowed_user.write({group_field: [(4, cls.allowed_group.id)]})

    @classmethod
    def _make_user(cls, login, group_refs):
        user = cls.env["res.users"].create({
            "name": login,
            "login": login,
            "email": "%s@example.com" % login,
        })
        field = "group_ids" if "group_ids" in user._fields else "groups_id"
        user.write({field: [(6, 0, [cls.env.ref(ref).id for ref in group_refs])]})
        return user

    # -- helpers -------------------------------------------------------
    def as_public(self, record):
        return record.with_user(self.public_user).with_context(
            website_id=self.website.id)

    def as_portal(self, record):
        return record.with_user(self.portal_user).with_context(
            website_id=self.website.id)

    def as_allowed(self, record):
        return record.with_user(self.allowed_user).with_context(
            website_id=self.website.id)

    def as_internal(self, record):
        return record.with_user(self.env.ref("base.user_admin")).with_context(
            website_id=self.website.id)

    def gate_off(self):
        self.website.b2b_gate_enabled = False

    def variant(self, template=None):
        return (template or self.product).product_variant_id
