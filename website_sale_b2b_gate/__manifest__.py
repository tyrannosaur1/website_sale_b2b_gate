# -*- coding: utf-8 -*-
{
    "name": "B2B Price Gate & Quote Requests",
    "version": "16.0.1.0.0",
    "summary": "Hide prices and add-to-cart from selected visitors and turn them into quote requests",
    "author": "ModForge",
    "license": "OPL-1",
    "category": "Website/Website",
    "depends": ["website_sale", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/quote_data.xml",
        "views/website_views.xml",
        "views/product_views.xml",
        "views/quote_views.xml",
        "views/templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_sale_b2b_gate/static/src/css/b2b_gate.css",
        ],
    },
    "images": [
        "static/description/screenshot_1.png",
        "static/description/screenshot_2.png",
    ],
    "installable": True,
    "application": False,
    "price": 49.0,
    "currency": "USD",
}
