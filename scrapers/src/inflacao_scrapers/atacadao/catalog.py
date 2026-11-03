"""Bounded target searches; drifting totals, duplicate SKUs and short pages fail visibly."""

from datetime import UTC, datetime

from ..adapters.catalog import check_page_identities, describe_page
from .parsing import parse_products, product_identity
from .source import fetch_products
from .stock import with_availability

PAGE_SIZE = 50


def validate_page(document, offset, limit, expected_total, seen):
    total = document["pageInfo"]["totalCount"]
    edges = document.get("edges")
    if type(total) is not int or total < 0 or not isinstance(edges, list):
        raise ValueError("Atacadão pagination malformed")
    if expected_total is not None and expected_total != total:
        raise ValueError("Atacadão catalog changed during pagination; collection incomplete")
    if offset > total or len(edges) != min(limit, total - offset):
        raise ValueError("Atacadão short/oversized page; collection incomplete")
    products = [edge["node"] for edge in edges]
    overlap = check_page_identities(
        [product_identity(product) for product in products], seen, "Atacadão"
    )
    if overlap:
        raise ValueError("Atacadão overlapping pages; collection incomplete")
    return products, total


def search_pages(requester, settings, target, query):
    seen, total, offset = set(), None, 0
    for _ in range(settings.max_search_pages):
        document, source_url = fetch_products(requester, settings, query, offset, PAGE_SIZE)
        observed_at = datetime.now(UTC)
        products, total = validate_page(document, offset, PAGE_SIZE, total, seen)
        products = with_availability(requester, settings, products, target)
        parsed = parse_products(products, settings, source_url, observed_at, target)
        yield describe_page(parsed, f"store={settings.store_id} offset={offset}", 0)
        offset += len(products)
        if offset >= total:
            return
    raise ValueError("Atacadão search page limit reached; collection incomplete")
