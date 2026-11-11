"""Convert branch-bound public previews into ingestion-v1 observation models for inspection."""

from uuid import uuid4

from ..adapters import ParsedPage
from ..models import Context, Observation
from .document import identity, public_url
from .offers import product_offers
from .values import availability, product_details, product_name


def parse_observations(storefront, source_url, observed_at, target=None):
    public_url(source_url)
    result = ParsedPage(warnings=list(storefront.warnings))
    for product in storefront.products:
        parse_candidate(product, storefront, source_url, observed_at, target, result)
    return result


def parse_candidate(source, storefront, source_url, observed_at, target, result):
    try:
        append_candidate(source, storefront, source_url, observed_at, target, result)
    except (ValueError, TypeError, ArithmeticError, KeyError) as error:
        result.issues.append(f"rappi product={source.get('product_id')}: {error}")


def append_candidate(source, storefront, source_url, observed_at, target, result):
    name = product_name(source)
    if target is not None and not target.matches(name):
        return
    warnings = []
    item = observation(source, storefront, source_url, observed_at, warnings)
    result.observations.append(item)
    result.warnings.extend(f"rappi product={source['product_id']}: {value}" for value in warnings)


def observation(source, storefront, source_url, observed_at, warnings):
    stock = availability(source)
    offers = []
    if stock == "in_stock":
        offers = product_offers(source, storefront, warnings)
    if stock == "unknown":
        warnings.append("Conflicting/missing Rappi availability; price omitted")
    return Observation(
        observation_id=uuid4(), observed_at=observed_at, collection_method="html",
        source_url=source_url, product_url=product_url(source, storefront),
        product=product_details(source, warnings), context=branch_context(storefront.branch),
        availability=stock, offers=offers,
    )


def product_url(source, storefront):
    master_id = identity(source.get("master_product_id"))
    url = storefront.product_urls.get(master_id)
    if url is None:
        raise ValueError("Missing Rappi source product link")
    return url


def branch_context(branch):
    return Context(
        seller_id=None, store_id="rappi:" + identity(branch["store_id"]),
        postal_code=None, city=branch.get("city") or None, state=None, channel="online",
    )
