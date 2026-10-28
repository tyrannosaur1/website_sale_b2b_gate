# -*- coding: utf-8 -*-
from odoo import fields, models

from .website import GATE_POLICIES


class ProductPublicCategory(models.Model):
    _inherit = "product.public.category"

    b2b_gate_policy = fields.Selection(
        GATE_POLICIES, string="B2B Price Policy", default="inherit", required=True,
        help="Hide or show the prices of the products of this category. A "
             "product without a policy of its own inherits this one.",
    )

    def _b2b_gate_effective_policy(self):
        """The first policy set on this category or one of its parents.

        A category that says nothing is not an answer: the walk goes up until
        a category states one, so a policy set on the root of a catalogue of
        four hundred leaves does not have to be repeated on every branch.
        """
        self.ensure_one()
        node, seen = self, set()
        while node and node.id not in seen:
            seen.add(node.id)
            if node.b2b_gate_policy != "inherit":
                return node.b2b_gate_policy
            node = node.parent_id
        return "inherit"
