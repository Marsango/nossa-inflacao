"""Pure parsing of captured grids into ingestion v1 observations."""

from decimal import InvalidOperation
from uuid import uuid4

from ..adapters import ParsedPage
from ..models import Context, Observation, Product
from ..packaging import package_metadata
from .offers import product_offers, sale_basis
from .values import product_identity, product_url


def parse_products(document, settings, source_url, observed_at, target=None):
    settings.require_context()
    products = document.get("productsSearchResult")
    if not isinstance(products, list):
        raise ValueError("Malformed Nagumo product array")
    result = ParsedPage()
    for product in products:
        parse_candidate(product, settings, source_url, observed_at, target, result)
    return result


def parse_candidate(product, settings, source_url, observed_at, target, result):
    identity = product.get("id") if isinstance(product, dict) else None
    try:
        append_candidate(product, settings, source_url, observed_at, target, result)
    except (ValueError, KeyError, TypeError, InvalidOperation) as error:
        result.issues.append(f"shop=nagumo sku={identity}: {error}")


def append_candidate(product, settings, source_url, observed_at, target, result):
    name = product["productName"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Missing Nagumo product name")
    if target is not None and not target.matches(name):
        return
    warnings = []
    observation = build_observation(product, settings, source_url, observed_at, warnings)
    result.observations.append(observation)
    result.warnings.extend(
        f"shop=nagumo sku={product_identity(product)}: {item}" for item in warnings
    )
    if observation.availability == "in_stock" and not observation.offers:
        result.warnings.append(f"shop=nagumo sku={product_identity(product)}: price unknown")


def build_observation(product, settings, source_url, observed_at, warnings):
    basis = sale_basis(product)
    return Observation(
        observation_id=uuid4(),
        observed_at=observed_at,
        collection_method="api",
        source_url=source_url,
        product_url=product_url(product),
        product=product_details(product, basis, warnings),
        context=pickup_context(settings),
        availability=availability(product),
        offers=product_offers(product, basis),
    )


def product_details(product, basis, warnings):
    name = product["productName"].strip()
    return Product(
        source_product_id=product_identity(product),
        name=name,
        brand=product.get("brand"),
        gtin=None,
        package=package_metadata(name, warnings) if basis == "package" else None,
    )


def pickup_context(settings):
    return Context(
        seller_id=None,
        store_id=settings.store_id,
        postal_code=settings.postal_code,
        city=settings.city,
        state=settings.state,
        channel="pickup",
    )


def availability(product):
    if product.get("available") is True:
        return "in_stock"
    if product.get("available") is False:
        return "out_of_stock"
    return "unknown"
