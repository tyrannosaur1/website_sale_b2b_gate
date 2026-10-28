# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models


class WebsiteQuoteRequest(models.Model):
    _name = "website.quote.request"
    _description = "Website quote request"
    _order = "id desc"

    name = fields.Char(
        string="Reference", copy=False, readonly=True, index=True,
        default=lambda self: _("New"),
    )
    website_id = fields.Many2one(
        "website", string="Website", required=True, ondelete="cascade", index=True,
        default=lambda self: self._default_website(),
    )
    company_id = fields.Many2one(
        "res.company", string="Company", related="website_id.company_id",
        store=True, index=True,
    )
    partner_id = fields.Many2one("res.partner", string="Customer", ondelete="set null")
    email = fields.Char(string="Email", required=True, index=True)
    phone = fields.Char(string="Phone")
    message = fields.Text(string="Message")
    state = fields.Selection(
        [("new", "New"), ("in_progress", "In Progress"),
         ("done", "Quoted"), ("cancelled", "Cancelled")],
        string="Status", default="new", required=True,
    )
    line_ids = fields.One2many(
        "website.quote.request.line", "request_id", string="Requested Products")

    @api.model
    def _default_website(self):
        from .website import current_website
        return current_website(self.env)

    @api.model
    def _b2b_gate_find_recent(self, email, website, minutes=5, now=None):
        """The request the same visitor already sent in the last few minutes.

        A double click, a browser that resends the POST on refresh and an
        impatient visitor all produce the same second request. Returning the
        request that is already there keeps the merchant's inbox honest -- one
        enquiry, one row -- and means the customer gets one answer to read.
        """
        email = (email or "").strip()
        if not email or not website:
            return self.browse()
        now = now or fields.Datetime.now()
        return self.sudo().search([
            ("email", "=ilike", email),
            ("website_id", "=", website.id),
            ("create_date", ">=", now - timedelta(minutes=minutes)),
        ], order="create_date desc, id desc", limit=1)

    @api.model
    def _b2b_gate_submit(self, website, email, phone=None, message=None,
                         template=None, quantity=1.0, now=None):
        """Create the request unless the same visitor sent one a moment ago.

        Returns ``(request, created)``. Runs with ``sudo()``: the caller is a
        public visitor who may read none of these records.
        """
        existing = self._b2b_gate_find_recent(email, website, now=now)
        if existing:
            return existing, False
        line = [(0, 0, {
            "product_tmpl_id": template.id or False,
            "quantity": quantity or 1.0,
        })] if template else []
        request = self.sudo().create({
            "website_id": website.id,
            "partner_id": self.env.user.partner_id.id,
            "email": (email or "").strip(),
            "phone": (phone or "").strip() or False,
            "message": (message or "").strip() or False,
            "line_ids": line,
        })
        return request, True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "website.quote.request") or _("New")
        return super().create(vals_list)


class WebsiteQuoteRequestLine(models.Model):
    _name = "website.quote.request.line"
    _description = "Website quote request line"

    request_id = fields.Many2one(
        "website.quote.request", string="Request", required=True,
        ondelete="cascade", index=True,
    )
    product_tmpl_id = fields.Many2one(
        "product.template", string="Product", ondelete="set null")
    name = fields.Char(
        string="Description", compute="_compute_name", store=True, readonly=False)
    quantity = fields.Float(string="Quantity", default=1.0, digits="Product Unit")

    @api.depends("product_tmpl_id")
    def _compute_name(self):
        for line in self:
            line.name = line.product_tmpl_id.name or ""
