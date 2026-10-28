# -*- coding: utf-8 -*-
"""The surfaces that are not the product page."""
from .common import GateCase

#: The two keys a suggestion line can carry a price in, one per series.
PRICE_MAPPING_KEYS = ("detail", "detail_strike", "search_item_metadata")


class TestSearchSurfaces(GateCase):

    def _options(self, **extra):
        options = {
            "displayImage": True,
            "displayDescription": True,
            "displayExtraLink": True,
            "displayDetail": True,
            "display_currency": self.website.currency_id,
        }
        options.update(extra)
        return options

    def test_suggestion_payload_has_no_price_line(self):
        """The search suggestion quotes the price in its `detail` line."""
        detail = self.as_public(self.env["product.template"])._search_get_detail(
            self.website, "name asc", self._options())
        for key in PRICE_MAPPING_KEYS:
            self.assertNotIn(key, detail["mapping"])

    def test_suggestion_payload_keeps_the_price_for_staff(self):
        detail = self.as_internal(self.env["product.template"])._search_get_detail(
            self.website, "name asc", self._options())
        self.assertTrue(
            any(key in detail["mapping"] for key in PRICE_MAPPING_KEYS),
            "the price line disappeared for a user who may see prices")

    def test_the_min_price_bound_is_dropped(self):
        """`/shop?min_price` must not work as a price oracle."""
        detail = self.as_public(self.env["product.template"])._search_get_detail(
            self.website, "name asc", self._options(min_price=200.0, max_price=300.0))
        self.assertNotIn("list_price", str(detail["base_domain"]))

    def test_the_min_price_bound_still_filters_for_staff(self):
        detail = self.as_internal(self.env["product.template"])._search_get_detail(
            self.website, "name asc", self._options(min_price=200.0))
        self.assertIn("list_price", str(detail["base_domain"]))

    def test_the_price_facet_is_switched_off(self):
        self.assertIs(
            self.as_public(self.website).is_view_active(
                "website_sale.filter_products_price"), False)
        self.assertTrue(
            self.as_internal(self.website).is_view_active(
                "website_sale.filter_products_price"),
            "staff lost the price filter")

    def test_the_price_facet_comes_back_when_the_gate_is_off(self):
        """Negative control: the switch, not the module, decides."""
        self.gate_off()
        self.assertTrue(
            self.as_public(self.website).is_view_active(
                "website_sale.filter_products_price"))
