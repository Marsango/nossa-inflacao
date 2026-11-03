"""Read-only storefront simulations confirm stock for the same seller and SKU."""

from ..vtex.json import decode_response
from .parsing import product_identity
from .source import validate_response


def selected_product(product, target):
    if target is None:
        return True
    name = product.get("name")
    return isinstance(name, str) and target.matches(name)


def request_stock(requester, settings, products):
    items = [
        {"id": product_identity(product), "quantity": 1, "seller": settings.seller_id}
        for product in products
    ]
    response = requester.request(
        "POST",
        settings.shop_url + "/api/checkout/pub/orderForms/simulation",
        params={"sc": settings.sales_channel},
        json={"items": items, "country": "BRA"},
        headers={"Cache-Control": "no-cache, max-age=0"},
    )
    validate_response(response)
    return decode_response(response.content)


def stock_by_identity(document, settings, products):
    items = document.get("items")
    if not isinstance(items, list):
        raise ValueError("Atacadão stock response malformed")
    result = {}
    for item in items:
        add_stock(item, settings, result)
    if set(result) != {product_identity(product) for product in products}:
        raise ValueError("Atacadão stock response does not match requested SKUs")
    return result


def add_stock(item, settings, result):
    identity = item.get("id")
    if not isinstance(identity, str) or identity in result:
        raise ValueError("Atacadão stock identity missing or repeated")
    if item.get("seller") != settings.seller_id:
        raise ValueError("Atacadão stock seller does not match verified branch")
    result[identity] = item.get("availability")


def with_availability(requester, settings, products, target=None):
    settings.require_context()
    selected = [product for product in products if selected_product(product, target)]
    if not selected:
        return products
    document = request_stock(requester, settings, selected)
    stock = stock_by_identity(document, settings, selected)
    return [
        {**product, "availability": stock.get(product_identity(product))} for product in products
    ]
