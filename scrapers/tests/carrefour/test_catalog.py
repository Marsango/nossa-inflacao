from copy import deepcopy

import pytest

from inflacao_scrapers.carrefour import catalog

from .conftest import OBSERVED_AT, captured_search


def full_page(count=15, total=16, page=1):
    product = captured_search()["products"][0]
    products = [new_product(product, page * 100 + index) for index in range(count)]
    return {
        "products": products,
        "totalCount": total,
        "pagination": {"current": {"index": page}, "perPage": 15, "count": (total + 14) // 15},
    }


def new_product(original, identity):
    product = deepcopy(original)
    product["productId"] = str(identity)
    product["items"][0]["itemId"] = str(identity)
    return product


def test_multiple_pages_advance_with_same_total_and_distinct_skus(settings, monkeypatch):
    documents = [full_page(), full_page(count=1, page=2)]
    monkeypatch.setattr(
        catalog,
        "fetch_products",
        lambda *args: (documents[args[-1] - 1], settings.shop_url, OBSERVED_AT),
    )
    pages = list(catalog.search_pages(object(), settings, None, "arroz", [2]))
    assert [len(page.observations) for page in pages] == [15, 1]
    assert not any(page.issues for page in pages)


@pytest.mark.parametrize("kind", ["short", "total", "repeated", "stuck", "size"])
def test_partial_or_drifting_pages_fail_visibly(kind):
    first = full_page()
    seen = set()
    catalog.validate_page(first, 1, None, seen)
    second = full_page(count=1, page=2)
    mutate_page(second, first, kind)
    with pytest.raises(ValueError):
        catalog.validate_page(second, 2, 16, seen)


def mutate_page(second, first, kind):
    if kind == "short":
        second["products"] = []
    if kind == "total":
        second["totalCount"] = 17
    if kind == "repeated":
        second["products"] = first["products"][:1]
    if kind == "stuck":
        second["pagination"]["current"]["index"] = 1
    if kind == "size":
        second["pagination"]["perPage"] = 50


def test_budget_exhaustion_does_not_become_success(settings, monkeypatch):
    monkeypatch.setattr(
        catalog, "fetch_products", lambda *args: (full_page(), settings.shop_url, OBSERVED_AT)
    )
    with pytest.raises(ValueError, match="budget"):
        list(catalog.search_pages(object(), settings, None, "arroz", [1]))
