# -*- coding: utf-8 -*-
from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _is_add_to_cart_allowed(self):
        """The gate's last line of defence at the model layer.

        The controllers refuse the gated product explicitly, but the shop also
        asks this method before it draws an add-to-cart button on a tile, and
        ``sale.order._cart_update`` asks it before it writes a line. Answering
        ``False`` here means no path -- not a quick-add button, not a wishlist
        move, not a direct ORM call through the cart -- can put the product in
        a cart behind the gate's back.
        """
        if self.product_tmpl_id._b2b_gate_blocks_cart():
            return False
        return super()._is_add_to_cart_allowed()

    def _b2b_gate_scrub_jsonld(self, data):
        """Drop the offer from a JSON-LD payload.

        A product page publishes its price to search engines through this
        dictionary. Removing the price block from the HTML while leaving the
        markup alone publishes the same price in a machine-readable form,
        which is the leak that outlives the visit.
        """
        if not isinstance(data, dict):
            return data
        data.pop("offers", None)
        for variant in data.get("hasVariant") or []:
            if isinstance(variant, dict):
                variant.pop("offers", None)
        return data

    def _prepare_jsonld_vals(self, **kwargs):
        data = super()._prepare_jsonld_vals(**kwargs)
        if self.product_tmpl_id._b2b_gate_hides_price():
            return self._b2b_gate_scrub_jsonld(data)
        return data
