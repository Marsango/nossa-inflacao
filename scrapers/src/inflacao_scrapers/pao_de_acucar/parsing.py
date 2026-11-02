"""Pure parsing of captured category responses."""

from decimal import InvalidOperation
from uuid import uuid4

from ..adapters import ParsedPage
from ..models import Context, Observation, Product
from ..packaging import package_metadata
from .offers import price_details, product_offers


def product_identity(product):
    identity = product.get("sku")
    if not isinstance(identity, str) or not identity.isascii() or not identity.isdigit():
        raise ValueError("Missing GPA source SKU")
    return identity


def parse_products(document, settings, source_url, observed_at, target):
    settings.require_context()
    result = ParsedPage()
    products = document.get("products")
    if not isinstance(products, list):
        raise ValueError("Missing GPA product list")
    for product in products:
        parse_candidate(product, settings, source_url, observed_at, target, result)
    return result


def parse_candidate(product, settings, source_url, observed_at, target, result):
    identity = product.get("sku") if isinstance(product, dict) else None
    try:
        append_candidate(product, settings, source_url, observed_at, target, result)
    except (ValueError, KeyError, TypeError, InvalidOperation) as error:
        result.issues.append(f"shop=pao-de-acucar sku={identity}: {error}")


def append_candidate(product, settings, source_url, observed_at, target, result):
    name = product["name"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Missing GPA product name")
    if target is not None and not target.matches(name):
        return
    warnings = []
    result.observations.append(
        build_observation(product, settings, source_url, observed_at, warnings)
    )
    result.warnings.extend(
        f"shop=pao-de-acucar sku={product_identity(product)}: {item}" for item in warnings
    )
    observation = result.observations[-1]
    if observation.availability == "in_stock" and not observation.offers and not warnings:
        result.warnings.append(f"shop=pao-de-acucar sku={product_identity(product)}: price unknown")


def build_observation(product, settings, source_url, observed_at, warnings):
    return Observation(
        observation_id=uuid4(),
        observed_at=observed_at,
        collection_method="api",
        source_url=source_url,
        product_url=product_url(product, settings),
        product=product_details(product, warnings),
        context=delivery_context(settings),
        availability=availability(product),
        offers=product_offers(product, warnings),
    )


def product_url(product, settings):
    url = product["urlDetails"]
    if not isinstance(url, str) or not url.startswith(settings.shop_url + "/produto/"):
        raise ValueError("Unexpected GPA product URL")
    return url


def product_details(product, warnings):
    _, basis = price_details(product)
    return Product(
        source_product_id=product_identity(product),
        name=product["name"],
        brand=product.get("brand"),
        gtin=None,
        package=package_metadata(product["name"], warnings) if basis == "package" else None,
    )


def delivery_context(settings):
    return Context(
        seller_id=None,
        store_id=settings.store_id,
        postal_code=settings.postal_code,
        city=settings.city,
        state=settings.state,
        channel="delivery",
    )


def availability(product):
    if product.get("stock") is True:
        return "in_stock"
    if product.get("stock") is False:
        return "out_of_stock"
    return "unknown"
