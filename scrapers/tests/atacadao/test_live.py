import pytest

from inflacao_scrapers.atacadao.adapter import discover
from inflacao_scrapers.atacadao.catalog import search_pages
from inflacao_scrapers.atacadao.source import prepare_context
from inflacao_scrapers.commands import create_client, create_requester

from .conftest import configuration

pytestmark = pytest.mark.live


def test_capital_branch_and_priced_sample(capital):
    settings = configuration(capital)
    with create_client(settings) as client:
        requester = create_requester(client, settings)
        prepared = prepare_context(requester, settings)
        page = discover(requester, prepared, "arroz", 3)
    assert page.observations and not page.issues
    assert all(o.context.seller_id == settings.seller_id for o in page.observations)
    assert any(o.offers for o in page.observations)
    assert any(o.availability == "in_stock" for o in page.observations)


def test_multiple_search_pages_keep_distinct_skus(settings):
    with create_client(settings) as client:
        requester = create_requester(client, settings)
        prepared = prepare_context(requester, settings)
        pages = list(search_pages(requester, prepared, None, "arroz"))
    assert len(pages) > 1
    assert not any(page.issues for page in pages)
    identities = [o.product.source_product_id for page in pages for o in page.observations]
    assert len(identities) == len(set(identities))


def test_advertised_weight_prices_remain_per_kilogram(settings):
    with create_client(settings) as client:
        requester = create_requester(client, settings)
        prepared = prepare_context(requester, settings)
        page = discover(requester, prepared, "banana", 3)
    assert page.observations and not page.issues
    assert all(o.product.package is None for o in page.observations)
    assert all(offer.basis == "kg" for o in page.observations for offer in o.offers)
