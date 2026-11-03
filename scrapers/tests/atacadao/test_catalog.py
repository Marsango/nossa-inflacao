from copy import deepcopy

import pytest

from inflacao_scrapers.atacadao.catalog import search_pages, validate_page

from .conftest import captured_products


def document(products, total=None):
    return {
        "pageInfo": {"totalCount": len(products) if total is None else total},
        "edges": [{"node": product} for product in products],
    }


def test_validates_complete_and_empty_results():
    products = captured_products("rice")
    actual, total = validate_page(document(products), 0, 50, None, set())
    assert actual == products and total == len(products)
    assert validate_page(document([]), 0, 50, None, set()) == ([], 0)


def test_rejects_short_pages_changed_totals_and_overlap():
    products = captured_products("rice")
    with pytest.raises(ValueError, match="short"):
        validate_page(document(products, 100), 0, 50, None, set())
    with pytest.raises(ValueError, match="changed"):
        validate_page(document(products), 0, 50, 99, set())
    seen = {products[0]["sku"]}
    with pytest.raises(ValueError, match="overlapping"):
        validate_page(document(products), 0, 50, None, seen)


def test_repeated_skus_on_a_page_fail():
    product = captured_products("rice")[0]
    with pytest.raises(ValueError, match="repeated"):
        validate_page(document([product, deepcopy(product)]), 0, 50, None, set())


def test_page_budget_exhaustion_is_not_success(settings, monkeypatch):
    from inflacao_scrapers.atacadao import catalog

    settings.max_search_pages = 1
    monkeypatch.setattr(catalog, "PAGE_SIZE", 1)
    monkeypatch.setattr(
        catalog, "with_availability", lambda requester, settings, products, target: products
    )
    monkeypatch.setattr(
        catalog,
        "fetch_products",
        lambda *args: (document(captured_products("rice")[:1], 2), settings.shop_url),
    )
    pages = search_pages(None, settings, None, "arroz")
    assert len(next(pages).observations) == 1
    with pytest.raises(ValueError, match="limit reached"):
        next(pages)
