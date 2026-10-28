# B2B Price Gate & Quote Requests

Hide prices and the add-to-cart button from visitors who are not your customers, and turn them into quote requests you can answer.

Odoo 16.0 – 20.0. One branch per series, the branch name is the series.

## What it does

- Three modes per website: hide prices only, hide prices and cart, or put the whole shop behind a login.
- Choose the customer groups that see the shop as usual; internal users always do, so the merchant can check the site.
- A price policy per product and per category: inherit, always show, always hide. A parent category covers its subtree, and a product in several categories follows the strictest one.
- Every price surface closes with the price block: shop tiles, search suggestions, structured data, the price filter and the variant selector.
- A quote form served outside `/shop`, so it is reachable even when the shop is behind a login. A submission creates a request with product and quantity, mails it once, and the same address submitting twice in five minutes gets one request and one email.
- Requests are listed in Sales › Quote Requests with a status you move as you answer them.

## Install

1. Copy the module into your addons path.
2. Update the app list, install **B2B Price Gate & Quote Requests**.
3. Website › Configuration › Settings: turn the gate on and pick the mode.

## Translations

Chinese, Spanish, German, French, Italian, Dutch, Polish, Brazilian Portuguese and Russian ship with the module.

## License

OPL-1. See `LICENSE`.

## Support

Open an issue on this repository.
