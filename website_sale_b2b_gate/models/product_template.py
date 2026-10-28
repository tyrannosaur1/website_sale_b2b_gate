# -*- coding: utf-8 -*-
from odoo import fields, models

from .website import GATE_POLICIES, current_website


class ProductTemplate(models.Model):
    _inherit = "product.template"

    b2b_gate_policy = fields.Selection(
        GATE_POLICIES, string="B2B Price Policy", default="inherit", required=True,
        help="Show or hide this product's price when the shop gate is on. "
             "Inherit asks the public categories, then the website.",
    )

    # ------------------------------------------------------------------
    # Policy
    # ------------------------------------------------------------------
    def _b2b_gate_category_policy(self):
        """The answer of the public categories, ``inherit`` when they have none.

        A product sits in several categories often enough (a brand and a
        family, say). ``hidden`` wins over ``visible``: a catalogue manager
        who hid a subtree means it, and a product that is both in a public
        teaser category and in the hidden wholesale category must not be
        exposed by the accident of a second link.
        """
        self.ensure_one()
        policies = {
            category._b2b_gate_effective_policy()
            for category in self.public_categ_ids
        }
        if "hidden" in policies:
            return "hidden"
        if policies and policies == {"visible"}:
            return "visible"
        return "inherit"

    def _b2b_gate_resolved_policy(self):
        self.ensure_one()
        if self.b2b_gate_policy != "inherit":
            return self.b2b_gate_policy
        return self._b2b_gate_category_policy()

    def _b2b_gate_hides_price(self):
        """Whether this product's price must stay out of this visitor's pages."""
        self.ensure_one()
        website = current_website(self.env)
        if not website or not website._b2b_gate_hides_prices():
            return False
        return self._b2b_gate_resolved_policy() != "visible"

    def _b2b_gate_blocks_cart(self):
        """Whether adding this product to the cart must be refused."""
        self.ensure_one()
        website = current_website(self.env)
        if not website or not website._b2b_gate_hides_cart():
            return False
        return self._b2b_gate_resolved_policy() != "visible"

    # ------------------------------------------------------------------
    # Price surfaces
    # ------------------------------------------------------------------
    def _get_combination_info(self, *args, **kwargs):
        """Scrub the price out of the payload the variant widget receives.

        The product page renders its price block from this dictionary, and so
        does ``/sale/get_combination_info_website``, the route the variant
        selector calls on every attribute change. Hiding the block in the
        template alone would leave that route answering the real price to
        anyone who presses F12 and switches a variant.
        """
        info = super()._get_combination_info(*args, **kwargs)
        if info and self._b2b_gate_hides_price():
            info.update({
                "price": 0.0,
                "list_price": 0.0,
                "compare_list_price": 0.0,
                "has_discounted_price": False,
                # 16 and 18 hide the price block and the add-to-cart button
                # when this flag is set; 20 replaced it with ``hide_price``.
                "prevent_zero_price_sale": True,
                "hide_price": True,
            })
            if "base_unit_price" in info:
                info["base_unit_price"] = 0.0
        return info

    def _search_get_detail(self, website, order, options):
        """Take the price out of the search payload and its price filter.

        One override covers the two surfaces that share this entry point:

        * the search suggestions, whose ``detail`` / ``search_item_metadata``
          line is the product's price. Asking for no detail drops the field
          from the mapping, so the suggestion JSON never carries it;
        * ``/shop?min_price=``, whose bounds land in this method as a domain on
          ``list_price``. Dropping them makes the parameter inert instead of a
          way to binary-search a hidden price.

        The gate is a property of the visitor, so the options are copied:
        mutating the caller's dict would change the page it is about to render.
        """
        gated = bool(website) and website.with_env(self.env)._b2b_gate_hides_prices()
        if gated:
            options = dict(options)
            options["displayDetail"] = False
            options.pop("min_price", None)
            options.pop("max_price", None)
        detail = super()._search_get_detail(website, order, options)
        if gated:
            # The flag above is not honoured by every series -- 20 adds the
            # price line unconditionally -- so the entries are taken out of
            # the mapping itself. ``detail_strike`` is the list price, which
            # 16 to 18 ship next to the price.
            for key in ("detail", "detail_strike", "search_item_metadata"):
                detail["mapping"].pop(key, None)
        return detail
