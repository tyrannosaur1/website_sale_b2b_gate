# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    b2b_gate_enabled = fields.Boolean(
        related="website_id.b2b_gate_enabled", readonly=False)
    b2b_gate_mode = fields.Selection(
        related="website_id.b2b_gate_mode", readonly=False)
    b2b_gate_allowed_group_ids = fields.Many2many(
        related="website_id.b2b_gate_allowed_group_ids", readonly=False)
    b2b_gate_message = fields.Html(
        related="website_id.b2b_gate_message", readonly=False)
    b2b_gate_quote_email = fields.Char(
        related="website_id.b2b_gate_quote_email", readonly=False)
