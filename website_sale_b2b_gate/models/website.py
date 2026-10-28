# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import fields, models

#: Price policies of a product and of a public category. ``inherit`` means
#: "ask the category, then the website"; the other two are final answers.
GATE_POLICIES = [
    ("inherit", "Inherit"),
    ("visible", "Always show prices"),
    ("hidden", "Always hide prices"),
]

#: What the gate does to a visitor who is not allowed to see prices.
GATE_MODES = [
    ("prices", "Hide prices only"),
    ("prices_and_cart", "Hide prices and add to cart"),
    ("whole_shop", "Whole shop requires a login"),
]

#: Rendered when the merchant did not write a message. It is stored in the
#: field's default rather than in the template so a translator gets one term
#: per sentence, exactly like a message the merchant typed.
DEFAULT_GATE_MESSAGE = (
    "<p>Prices are reserved for approved business customers.</p>"
    "<p>Send us a request and we will answer with a quotation.</p>"
)


def current_website(env):
    """Return the website the current call belongs to.

    Inside a request this is the site the request was routed to. Outside one --
    a shell, a cron, a test that never builds a request -- it falls back to the
    first website, which is what the storefront would have used anyway.
    """
    website = env["website"].get_current_website()
    if not website:
        website = env["website"].search([], limit=1)
    return website


class Website(models.Model):
    _inherit = "website"

    b2b_gate_enabled = fields.Boolean(
        string="B2B Price Gate", default=False,
        help="Hide prices, and optionally the cart, from visitors who are not "
             "allowed to see them, and offer a quote request instead.",
    )
    b2b_gate_mode = fields.Selection(
        GATE_MODES, string="Gate Mode", default="prices_and_cart", required=True,
        help="Hide prices only: visitors can still fill a cart and see prices there.\n"
             "Hide prices and add to cart: the add-to-cart routes refuse the "
             "product and the customer is sent to the quote form.\n"
             "Whole shop requires a login: every /shop page redirects to the "
             "login screen until the visitor signs in.",
    )
    b2b_gate_allowed_group_ids = fields.Many2many(
        "res.groups", relation="website_b2b_gate_groups",
        column1="website_id", column2="group_id",
        string="Groups That See Prices",
        help="Visitors who belong to one of these groups see the shop as usual. "
             "Internal users always see it, so the merchant can check the site "
             "without logging out. Leave empty to show prices to nobody but "
             "internal users.",
    )
    b2b_gate_message = fields.Html(
        string="Gate Message", translate=True, default=DEFAULT_GATE_MESSAGE,
        help="Replaces the price on the product page of a gated product.",
    )
    b2b_gate_quote_email = fields.Char(
        string="Quote Requests Email",
        help="Address that receives the quote requests. Defaults to the "
             "company email address.",
    )

    # ------------------------------------------------------------------
    # Who sees what
    # ------------------------------------------------------------------
    def _b2b_gate_user_is_allowed(self):
        """Whether the current user belongs to the side that sees prices."""
        self.ensure_one()
        user = self.env.user
        if user._is_public():
            return False
        # Staff can always check the storefront. They can read every price in
        # the back end anyway, so hiding it from them would only make the
        # configuration impossible to verify.
        if user.has_group("base.group_user"):
            return True
        # sudo: the answer decides what the visitor is shown, so it must not
        # depend on what the visitor himself may read. A portal customer who
        # cannot read one of the configured groups was treated as "not
        # allowed" and lost the prices the merchant had granted him.
        groups = self.sudo().b2b_gate_allowed_group_ids
        if not groups:
            return False
        # 16 and 17 only expose the groups granted directly; 18 and later
        # also carry the ones inherited from another group.
        user = user.sudo()
        user_groups = (
            user.all_group_ids if "all_group_ids" in user._fields
            else user.groups_id)
        return bool(groups & user_groups)

    def _b2b_gate_hides_prices(self):
        """Whether this visitor must not be shown a price anywhere."""
        self.ensure_one()
        if not self.b2b_gate_enabled:
            return False
        if self.b2b_gate_mode == "whole_shop":
            # The whole-shop mode is a login wall, not a price rule: once the
            # visitor is signed in, the shop is the ordinary shop.
            return self.env.user._is_public()
        return not self._b2b_gate_user_is_allowed()

    def _b2b_gate_hides_cart(self):
        """Whether this visitor must be refused at the add-to-cart routes."""
        self.ensure_one()
        if not self.b2b_gate_enabled:
            return False
        if self.b2b_gate_mode == "prices":
            # Prices only: the point of the mode is that the price is revealed
            # by the cart, so the cart has to keep working.
            return False
        if self.b2b_gate_mode == "whole_shop":
            return self.env.user._is_public()
        return not self._b2b_gate_user_is_allowed()

    def _b2b_gate_requires_login(self):
        """Whether /shop must send this visitor to the login screen first."""
        self.ensure_one()
        return (
            bool(self.b2b_gate_enabled)
            and self.b2b_gate_mode == "whole_shop"
            and self.env.user._is_public()
        )

    def _b2b_gate_message_html(self):
        """The gate message as markup, ready for ``t-out``."""
        self.ensure_one()
        return Markup(self.b2b_gate_message or DEFAULT_GATE_MESSAGE)

    def _b2b_gate_quote_email_to(self):
        """Address the quote notifications are sent to."""
        self.ensure_one()
        return (self.b2b_gate_quote_email or "").strip() or (self.company_id.email or "")

    # ------------------------------------------------------------------
    # Storefront switches
    # ------------------------------------------------------------------
    def is_view_active(self, view_key):
        """The price facet is a price: switch it off while prices are hidden.

        The shop reads this flag before it computes the available price range
        and before it renders the range slider, so one answer removes both the
        slider and the filtering it drives. Answering here -- instead of
        inheriting the slider template -- keeps the two halves in step: a
        disabled slider whose bounds still filter would leak the catalogue's
        price spread one query at a time.
        """
        if view_key == "website_sale.filter_products_price" and self._b2b_gate_hides_prices():
            return False
        return super().is_view_active(view_key)
