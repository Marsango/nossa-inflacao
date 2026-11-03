"""Pure FastStore parsing with strict seller context and conservative availability."""

import re
from decimal import InvalidOperation
from uuid import uuid4

from ..adapters import ParsedPage
from ..models import Context, Observation, Product
from ..packaging import package_metadata
from .offers import product_offers
from .values import sale_basis


def product_identity(product):
    identity = product.get("sku")
    if not isinstance(identity, str) or not re.fullmatch(r"[0-9]+", identity):
        raise ValueError("Atacadão SKU missing")
    if product.get("id") != identity:
        raise ValueError("Atacadão product and SKU identities disagree")
    return identity


def parse_products(products, settings, source_url, observed_at, target=None):
    settings.require_context()
    result = ParsedPage()
    for product in products:
        parse_candidate(product, settings, source_url, observed_at, target, result)
    return result


def parse_candidate(product, settings, source_url, observed_at, target, result):
    try:
        append_candidate(product, settings, source_url, observed_at, target, result)
    except (ValueError, KeyError, TypeError, InvalidOperation) as error:
        result.issues.append(f"shop=atacadao store={settings.store_id}: {error}")


def append_candidate(product, settings, source_url, observed_at, target, result):
    name = product["name"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Atacadão product name missing")
    if target is not None and not target.matches(name):
        return
    append_product(product, settings, source_url, observed_at, result)


def append_product(product, settings, source_url, observed_at, result):
    warnings = []
    result.observations.append(
        Observation(
            observation_id=uuid4(),
            observed_at=observed_at,
            collection_method="api",
            source_url=source_url,
            product_url=product_url(product, settings),
            product=product_details(product, warnings),
            context=branch_context(settings),
            availability=availability(product),
            offers=product_offers(product, settings),
        )
    )
    result.warnings.extend(f"sku={product_identity(product)}: {warning}" for warning in warnings)


def product_url(product, settings):
    slug = product["slug"]
    if not isinstance(slug, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", slug):
        raise ValueError("Atacadão product URL malformed")
    return settings.shop_url + "/" + slug + "/p"


def product_details(product, warnings):
    basis, _ = sale_basis(product)
    return Product(
        source_product_id=product_identity(product),
        name=product["name"],
        brand=product["brand"].get("name") or None,
        gtin=None,
        package=package_metadata(product["name"], warnings) if basis == "package" else None,
    )


def branch_context(settings):
    return Context(
        seller_id=settings.seller_id,
        store_id=settings.store_id,
        postal_code=None,
        city=settings.city,
        state=settings.state,
        channel="online",
    )


def availability(product):
    value = product.get("availability")
    if value in ("available", "https://schema.org/InStock"):
        return "in_stock"
    if value in ("withoutStock", "unavailable", "https://schema.org/OutOfStock"):
        return "out_of_stock"
    return "unknown"
