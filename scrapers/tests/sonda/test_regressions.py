"""Production formats captured on 2026-11-02, without fulfillment claims."""

import re

import httpx
import pytest
from stores.conftest import FIXTURES

from inflacao_scrapers.sonda.catalog import catalog_pages, listing_pages
from inflacao_scrapers.sonda.html import Document, suffix_nodes
from inflacao_scrapers.sonda.offers import CONTEXT_NOTE
from inflacao_scrapers.sonda.pages import CatalogChanged, category_paths
from inflacao_scrapers.sonda.parsing import parse_cards
from inflacao_scrapers.transport import Requester

from .test_catalog import last_page, overlapping_second_page
from .test_parsing import NOW, PATH, settings, source


def regression_source():
    return (FIXTURES / "sonda-regressions.html").read_text()


def regression_page():
    cards = suffix_nodes(Document(regression_source()).root, "_divGeral")
    return parse_cards(cards, settings(), settings().shop_url + "/delivery/categoria/Limpeza", NOW)


def test_full_navigation_includes_departments_absent_from_featured_menu():
    paths = category_paths(regression_source())
    assert "/delivery/categoria/Higiene_e_Beleza" in paths
    assert "/delivery/categoria/Bebidas_Nao_Alcoolicas" in paths
    assert "/delivery/categoria/Padaria" in paths
    assert len(paths) == len(set(paths)) == 14


def test_quantity_average_is_conditional_and_second_unit_price_is_not_a_uniform_price():
    page = regression_page()
    assert not page.issues
    second, quantity, dairy = page.observations
    assert [offer.amount for offer in second.offers] == ["5.98"]
    assert "2ª UNIDADE sai por: 4,78" in second.offers[0].conditions.description
    assert [offer.amount for offer in quantity.offers] == ["18.60", "12.40"]
    assert quantity.offers[1].conditions.minimum_quantity == "3"
    assert quantity.offers[0].conditions.minimum_quantity is None
    assert dairy.offers[0].amount == "3.51" and dairy.product.package is None


def changing_response(request, calls, stable):
    calls.append(request.url.path)
    if request.url.path == PATH:
        return httpx.Response(200, text=re.sub(r"\bde \d+", "de 2", source()))
    if stable and len(calls) > 2:
        return httpx.Response(200, text=overlapping_second_page())
    document = source().replace('value="1"', 'value="2"')
    document = re.sub(r"\bde \d+", "de 3", document)
    return httpx.Response(200, text=document)


def test_a_changed_department_restarts_once_and_can_complete():
    calls = []
    transport = httpx.MockTransport(lambda request: changing_response(request, calls, True))
    with httpx.Client(transport=transport) as client:
        pages = list(listing_pages(Requester(client, interval=0), settings(), None, PATH, [10]))
    assert len(calls) == 4
    assert sum(bool(page.observations) for page in pages) == 3
    assert any(
        "restarting department once" in warning for page in pages for warning in page.warnings
    )
    assert not any(page.issues for page in pages)


def test_a_continuously_changing_department_still_fails_within_the_retry_budget():
    calls = []
    transport = httpx.MockTransport(lambda request: changing_response(request, calls, False))
    with httpx.Client(transport=transport) as client, pytest.raises(CatalogChanged):
        pages = listing_pages(Requester(client, interval=0), settings(), None, PATH, [10])
        list(pages)
    assert len(calls) == 4


def test_public_catalog_provenance_is_reported_once_across_departments():
    transport = httpx.MockTransport(lambda _: httpx.Response(200, text=last_page(source())))
    configuration = settings(category_paths=[PATH, "/delivery/categoria/Limpeza"])
    with httpx.Client(transport=transport) as client:
        pages = list(catalog_pages(Requester(client, interval=0), configuration, None))
    assert sum(warning == CONTEXT_NOTE for page in pages for warning in page.warnings) == 1
