"""Pure product parsing; preserve actual SKU, delivery region, stock and offer conditions."""

from datetime import datetime
from decimal import InvalidOperation
from urllib.parse import urlsplit
from uuid import uuid4

from ..adapters import ParsedPage
from ..models import Context, Observation, Product
from ..packaging import package_metadata
from .config import CarrefourSettings
from .offers import product_offers
from .values import identity, package_name, sale_basis, select_seller, stock


def parse_products(
    products: list[dict],
    settings: CarrefourSettings,
    source_url: str,
    observed_at: datetime,
    target=None,
) -> ParsedPage:
    result = ParsedPage()
    for product in products:
        parse_candidate(product, settings, source_url, observed_at, target, result)
    return result


def parse_candidate(product, settings, source_url, observed_at, target, result):
    try:
        append_candidate(product, settings, source_url, observed_at, target, result)
    except (ValueError, KeyError, TypeError, InvalidOperation) as error:
        result.issues.append(f"shop=carrefour city={settings.city}: {error}")


def append_candidate(product, settings, source_url, observed_at, target, result):
    name = product["productName"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Carrefour product name missing")
    if target is not None and not target.matches(name):
        return
    append_items(product, settings, source_url, observed_at, result)


def append_items(product, settings, source_url, observed_at, result):
    identity(product.get("productId"))
    items = product.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Carrefour product has no SKUs")
    for item in items:
        append_item(product, item, settings, source_url, observed_at, result)


def append_item(product, item, settings, source_url, observed_at, result):
    seller = select_seller(item, settings.seller_id)
    warnings = []
    observation = Observation(
        observation_id=uuid4(),
        observed_at=observed_at,
        collection_method="browser",
        source_url=source_url,
        product_url=product_url(product, settings),
        product=product_details(product, item, warnings),
        context=delivery_context(settings, seller.get("sellerId")),
        availability=stock(seller["commertialOffer"]),
        offers=product_offers(item, seller),
    )
    result.observations.append(observation)
    result.warnings.extend(f"sku={item['itemId']}: {warning}" for warning in warnings)


def product_details(product, item, warnings):
    name = item.get("name") or product["productName"]
    return Product(
        source_product_id=identity(item.get("itemId")),
        name=name,
        brand=product.get("brand") or None,
        gtin=None,
        package=package_metadata(package_name(name), warnings)
        if sale_basis(item) == "package"
        else None,
    )


def product_url(product, settings):
    link = product.get("link")
    if not isinstance(link, str):
        raise ValueError("Carrefour product link missing")
    parts = urlsplit(link)
    if (
        parts.scheme
        or parts.netloc
        or not parts.path.startswith("/")
        or not parts.path.endswith("/p")
    ):
        raise ValueError("Carrefour product link escaped the storefront")
    return settings.shop_url + link


def delivery_context(settings, seller_id):
    return Context(
        seller_id=seller_id,
        store_id=settings.store_id,
        postal_code=settings.postal_code,
        city=settings.city,
        state=settings.state,
        channel="delivery",
    )
