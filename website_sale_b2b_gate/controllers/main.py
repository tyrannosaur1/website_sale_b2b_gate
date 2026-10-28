# -*- coding: utf-8 -*-
import logging
import re

from werkzeug.exceptions import Forbidden

from odoo import _, http
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.website_sale.controllers.cart import Cart as CartController
from odoo.addons.website_sale.controllers.main import WebsiteSale as WebsiteSaleController

from ..models.website import current_website

_logger = logging.getLogger(__name__)

#: Deliberately simple. A quote request is a lead, not a payment: what matters
#: is that the merchant can answer it, so the check rejects what cannot be an
#: address and accepts everything else.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _b2b_gate_order_blocked(order):
    """Whether ``order`` holds a line the gate refuses to let through.

    Every route that moves a cart towards payment asks this one question, so
    the checkout page, the confirmation step and the payment step cannot
    disagree about which carts are blocked.
    """
    return bool(order) and bool(order.order_line.filtered(
        lambda line: line.product_id.product_tmpl_id._b2b_gate_blocks_cart()))


class WebsiteSaleB2BGate(WebsiteSaleController):
    """The shop's own routes, refused for the visitors the gate covers."""

    # ------------------------------------------------------------------
    # Shop list
    # ------------------------------------------------------------------
    @http.route()
    def shop(self, page=0, category=None, search="", min_price=0.0,
             max_price=0.0, **post):
        """Drop the price bounds before the shop filters on them.

        ``min_price`` is read from the query string and turned into a domain
        on ``list_price``; a visitor could otherwise bisect the hidden prices
        of the catalogue one request at a time. The filter widget is switched
        off by :meth:`website.is_view_active`, but the parameter still arrives,
        so it is dropped here as well -- a hidden slider and an inert
        parameter are two different promises.
        """
        website = current_website(request.env)
        if website._b2b_gate_hides_prices():
            min_price, max_price = 0.0, 0.0
            post.pop("min_price", None)
            post.pop("max_price", None)
        return super().shop(
            page=page, category=category, search=search,
            min_price=min_price, max_price=max_price, **post)

    # ------------------------------------------------------------------
    # Cart
    # ------------------------------------------------------------------
    # From 19 the cart has its own controller and its add route already asks
    # ``product._is_add_to_cart_allowed()`` before it writes a line; the model
    # override answers False for a gated product, so the route refuses with a
    # JSON-RPC error instead of adding it quietly. The quantity update of a
    # line that is already in the cart still needs a guard here.
    @http.route(["/shop/checkout"], type="http", auth="public",
                methods=["GET"], website=True, sitemap=False)
    def checkout(self, **post):
        """A cart the gate has since closed cannot be paid for.

        The lines may predate the gate -- the merchant switched the mode on
        while a visitor was shopping -- so the check is made on the way into
        checkout instead of when the line was written.
        """
        order = request.cart
        if _b2b_gate_order_blocked(order):
            return request.redirect("/shop/cart?b2b_gate=checkout_blocked")
        return super().checkout(**post)

    @http.route(["/shop/payment"], type="http", auth="public",
                website=True, sitemap=False)
    def shop_payment(self, **post):
        """The payment step is a URL of its own, not a child of checkout.

        A visitor who kept the address step in a tab, or who calls the payment
        URL directly, would otherwise reach the payment form for a cart the
        gate has closed. The answer is the checkout page's: back to the cart,
        where the line can be removed or quoted.
        """
        order = request.cart
        if _b2b_gate_order_blocked(order):
            return request.redirect("/shop/cart?b2b_gate=payment_blocked")
        return super().shop_payment(**post)

    @http.route(["/shop/payment/validate"], type="http",
                auth="public", website=True, sitemap=False)
    def shop_payment_validate(self, sale_order_id=None, **post):
        """Never confirm a gated cart, even when there is nothing to pay.

        A zero-total cart -- a full discount, a free sample -- is confirmed by
        this route without any transaction, which makes it the place where a
        cart really becomes an order without a payment. A cart that already
        has a transaction is left alone: the money is in flight, and refusing
        here would take the payment and lose the order.
        """
        order = self._b2b_gate_order_for_validation(sale_order_id)
        if (order and order.state in ("draft", "sent")
                and not order.get_portal_last_transaction()
                and _b2b_gate_order_blocked(order)):
            return request.redirect("/shop/cart?b2b_gate=payment_blocked")
        return super().shop_payment_validate(
            sale_order_id=sale_order_id, **post)

    def _b2b_gate_order_for_validation(self, sale_order_id=None):
        """The order core is about to confirm, resolved the way core does.

        The route takes the id from the query string or, failing that, from
        the session, so both are read here and the guard sees the record the
        call is about.
        """
        if sale_order_id:
            return request.env["sale.order"].sudo().browse(
                int(_to_float(sale_order_id))).exists()
        order = request.cart
        if not order and request.session.get("sale_last_order_id"):
            order = request.env["sale.order"].sudo().browse(
                request.session["sale_last_order_id"]).exists()
        return order


class WebsiteSaleB2BGateCart(CartController):
    """The cart controller of 19 and 20."""

    @http.route(["/shop/cart/update"], type="jsonrpc", auth="public",
                methods=["POST"], website=True, sitemap=False)
    def update_cart(self, line_id, quantity, product_id=None, **kwargs):
        order = request.cart
        line = order and order.order_line.filtered(
            lambda candidate: candidate.id == int(_to_float(line_id)))[:1]
        if (line and _to_float(quantity) > 0
                and line.product_id.product_tmpl_id._b2b_gate_blocks_cart()):
            raise UserError(
                _("This product is only available as a quote request."))
        return super().update_cart(
            line_id=line_id, quantity=quantity, product_id=product_id, **kwargs)


class WebsiteSaleB2BQuote(http.Controller):
    """The quote form, deliberately outside /shop.

    ``whole_shop`` sends every /shop page to the login screen, so the form the
    visitor is supposed to use instead must not live there.
    """

    def _b2b_gate_template(self, template_id):
        try:
            template = request.env["product.template"].browse(int(template_id))
        except (TypeError, ValueError):
            return request.env["product.template"]
        return template.exists().filtered("sale_ok")

    def _b2b_gate_render_form(self, template, error=None, email=None,
                              phone=None, message=None, quantity=None):
        return request.render("website_sale_b2b_gate.quote_form", {
            "product": template,
            "error": error,
            "email": email or "",
            "phone": phone or "",
            "message": message or "",
            "quantity": quantity or 1,
            "website": current_website(request.env),
        })

    @http.route("/b2b/quote", type="http", auth="public", website=True, sitemap=False)
    def quote_form(self, template_id=None, **kw):
        return self._b2b_gate_render_form(self._b2b_gate_template(template_id))

    @http.route("/b2b/quote/submit", type="http", auth="public", methods=["POST"],
                website=True, csrf=True, sitemap=False)
    def quote_submit(self, email=None, phone=None, message=None,
                     template_id=None, quantity=None, **kw):
        template = self._b2b_gate_template(template_id)
        email = (email or "").strip()
        if not EMAIL_RE.match(email):
            return self._b2b_gate_render_form(
                template, error=_("Please enter a valid email address."),
                email=email, phone=phone, message=message, quantity=quantity)

        website = current_website(request.env)
        quote, created = request.env["website.quote.request"]._b2b_gate_submit(
            website, email, phone=phone, message=message,
            template=template, quantity=_to_float(quantity, 1.0) or 1.0)
        if created:
            self._b2b_gate_notify(quote, website)
        return request.redirect("/b2b/quote/thanks", code=303)

    def _b2b_gate_notify(self, quote, website):
        """Send the request to the address the merchant configured.

        A mail that cannot leave -- no server, a wrong address -- must not
        cost the merchant the lead: the request is already stored, so the
        failure is logged and the visitor still reaches the thank-you page.
        """
        email_to = website._b2b_gate_quote_email_to()
        if not email_to:
            _logger.info("Quote request %s has no notification address", quote.name)
            return
        template = request.env.ref(
            "website_sale_b2b_gate.mail_template_quote_request",
            raise_if_not_found=False)
        try:
            if template:
                template.sudo().send_mail(
                    quote.id, email_values={"email_to": email_to}, force_send=True)
            else:  # pragma: no cover - the template ships with the module
                request.env["mail.mail"].sudo().create({
                    "subject": _("Quote request %s") % quote.name,
                    "email_to": email_to,
                    "body_html": quote.message or "",
                }).send()
        except Exception:
            _logger.exception(
                "Quote request %s could not be emailed to %s", quote.name, email_to)

    @http.route("/b2b/quote/thanks", type="http", auth="public", website=True, sitemap=False)
    def quote_thanks(self, **kw):
        return request.render("website_sale_b2b_gate.quote_thanks", {
            "website": current_website(request.env),
        })
