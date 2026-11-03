"""Stream bounded target searches through one isolated delivery session per city."""

from ..adapters.catalog import check_page_identities
from .parsing import parse_products
from .session import open_session
from .source import fetch_products
from .values import identity

PAGE_SIZE = 15


def validate_page(document, page, expected_total, seen):
    total = document.get("totalCount")
    products = document.get("products")
    if type(total) is not int or total < 0 or not isinstance(products, list):
        raise ValueError("Carrefour catalog/pagination malformed")
    if expected_total is not None and total != expected_total:
        raise ValueError("Carrefour catalog total changed during pagination")
    validate_pagination(document.get("pagination"), page, total)
    expected = max(0, min(PAGE_SIZE, total - (page - 1) * PAGE_SIZE))
    if len(products) != expected:
        raise ValueError("Carrefour short or oversized page; collection incomplete")
    if check_page_identities([identity(p.get("productId")) for p in products], seen, "Carrefour"):
        raise ValueError("Carrefour overlapping pages; collection incomplete")
    return products, total


def validate_pagination(pagination, page, total):
    if not isinstance(pagination, dict):
        raise ValueError("Carrefour pagination absent")
    current = pagination.get("current") or {}
    if type(current.get("index")) is not int or current["index"] != page:
        raise ValueError("Carrefour pagination did not advance")
    expected_count = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if pagination.get("perPage") != PAGE_SIZE or pagination.get("count") != expected_count:
        raise ValueError("Carrefour page size/count changed")


def search_pages(driver, settings, target, query, budget):
    seen, total, page = set(), None, 1
    while total is None or (page - 1) * PAGE_SIZE < total:
        require_search_budget(settings, page)
        consume_budget(budget)
        document, url, observed_at = fetch_products(driver, settings, query, page)
        products, total = validate_page(document, page, total, seen)
        yield parse_products(products, settings, url, observed_at, target)
        page += 1


def require_search_budget(settings, page):
    if page > settings.max_search_pages:
        raise ValueError("Carrefour search page budget exhausted; collection incomplete")


def consume_budget(budget):
    if budget[0] <= 0:
        raise ValueError("Carrefour run page budget exhausted; collection incomplete")
    budget[0] -= 1


def catalog_pages(requester, settings, scope):
    budget = [settings.max_catalog_pages]
    with open_session(settings) as driver:
        yield from scope_pages(driver, settings, scope, budget)


def scope_pages(driver, settings, scope, budget):
    for target in scope.targets:
        yield from target_pages(driver, settings, target, budget)


def target_pages(driver, settings, target, budget):
    for query in target.search_queries:
        yield from query_pages(driver, settings, target, query, budget)


def query_pages(driver, settings, target, query, budget):
    try:
        yield from search_pages(driver, settings, target, query, budget)
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(f"Carrefour target={target.id} query={query}: {error}") from error
