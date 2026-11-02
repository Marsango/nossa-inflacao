"""Pure parsing of captured Hirota responses into ingestion v1 observations."""

import re
from decimal import InvalidOperation
from uuid import uuid4

from ..adapters import ParsedPage
from ..models import Context, Observation, Product
from ..packaging import package_metadata
from .offers import portion_priced, product_offers, sale_basis
from .values import product_identity, product_path, source_gtin


def parse_products(document, settings, source_url, observed_at, target=None):
    settings.source_headers()
    products = document.get("data")
    if document.get("success") is not True or not isinstance(products, list):
        raise ValueError("Malformed Hirota product array")
    result = ParsedPage()
    for product in products:
        parse_candidate(product, settings, source_url, observed_at, target, result)
    return result


def parse_candidate(product, settings, source_url, observed_at, target, result):
    identity = product.get("produto_id") if isinstance(product, dict) else None
    try:
        append_candidate(product, settings, source_url, observed_at, target, result)
    except (ValueError, KeyError, TypeError, InvalidOperation) as error:
        result.issues.append(f"shop=hirota sku={identity}: {error}")


def append_candidate(product, settings, source_url, observed_at, target, result):
    name = product["descricao"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Missing product name")
    if target is not None and not target.matches(name):
        return
    warnings = []
    observation = build_observation(product, settings, source_url, observed_at, warnings)
    result.observations.append(observation)
    result.warnings.extend(
        f"shop=hirota sku={product_identity(product)}: {item}" for item in warnings
    )
    if observation.availability == "in_stock" and not observation.offers:
        result.warnings.append(f"shop=hirota sku={product_identity(product)}: price unknown")


def build_observation(product, settings, source_url, observed_at, warnings):
    basis = sale_basis(product)
    return Observation(
        observation_id=uuid4(),
        observed_at=observed_at,
        collection_method="api",
        source_url=source_url,
        product_url=settings.shop_url + product_path(product),
        product=product_details(product, basis, warnings),
        context=pickup_context(settings),
        availability=availability(product),
        offers=product_offers(product, basis, warnings),
    )


def product_details(product, basis, warnings):
    name = product["descricao"].strip()
    package = product_package(product, basis, warnings)
    return Product(
        source_product_id=product_identity(product),
        name=name,
        brand=product.get("marca"),
        gtin=source_gtin(product.get("codigo_barras")),
        package=package,
    )


def product_package(product, basis, warnings):
    if basis != "package" or portion_priced(product, basis):
        return None
    return fixed_package(product["descricao"].strip(), warnings)


def fixed_package(name, warnings):
    contents = re.sub(r"(\d+(?:[.,]\d+)?)\s*litros?\b", r"\1l", name, flags=re.I)
    return package_metadata(contents, warnings)


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
    if product.get("disponivel") is True:
        return "in_stock"
    if product.get("disponivel") is False:
        return "out_of_stock"
    return "unknown"
