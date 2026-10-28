# -*- coding: utf-8 -*-
from urllib.parse import quote as url_quote

from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect as werkzeug_redirect

from odoo import models
from odoo.http import request

from .website import current_website


class GateLoginRequired(HTTPException):
    """A 303 that Odoo serves as a response, not as an error page.

    ``ir.http._pre_dispatch`` is called for its side effects: the router runs
    it and then calls the endpoint, so there is no return value to give a
    redirect back to it. What the request machinery does support is an
    ``HTTPException`` whose ``code`` is ``None`` -- that one is served as a
    valid response instead of being passed to ``_handle_error``. It is the
    same door ``odoo.http.abort(response)`` uses, without depending on that
    helper, which moved between series.
    """

    code = None

    def __init__(self, location):
        super().__init__()
        self.location = location

    def get_response(self, environ=None, scope=None):
        return werkzeug_redirect(self.location, code=303)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _pre_dispatch(cls, rule, args):
        super()._pre_dispatch(rule, args)
        cls._b2b_gate_login_wall()

    @classmethod
    def _b2b_gate_login_wall(cls):
        """Send an anonymous visitor to the login screen in ``whole_shop`` mode.

        Only GET and HEAD are redirected. The shop's POST routes carry a cart
        payload, and a redirect would drop it silently; those are refused by
        the controllers' own gate instead, which answers with the reason.
        """
        path = request.httprequest.path or ""
        if not (path == "/shop" or path.startswith("/shop/")):
            return
        if request.httprequest.method not in ("GET", "HEAD"):
            return
        website = current_website(request.env)
        if not website or not website._b2b_gate_requires_login():
            return
        raise GateLoginRequired("/web/login?redirect=%s" % url_quote(path))
