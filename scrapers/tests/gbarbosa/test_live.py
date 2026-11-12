import pytest

from inflacao_scrapers.commands import create_client, create_requester
from inflacao_scrapers.gbarbosa.adapter import ADAPTER

pytestmark = pytest.mark.live


def test_delivery_region_and_packaged_prices_are_reachable(settings):
    with create_client(settings) as client:
        requester = create_requester(client, settings)
        prepared = ADAPTER.prepare(requester, settings)
        page = ADAPTER.discover(requester, prepared, "arroz branco", 3)
    assert not page.issues
    assert page.observations
    assert any(item.offers and item.availability == "in_stock" for item in page.observations)
    assert all(item.context.postal_code == settings.postal_code for item in page.observations)


def test_advertised_weight_prices_are_reachable(settings):
    with create_client(settings) as client:
        requester = create_requester(client, settings)
        prepared = ADAPTER.prepare(requester, settings)
        page = ADAPTER.discover(requester, prepared, "banana", 3)
    assert not page.issues
    assert any(item.offers for item in page.observations)
    assert all(offer.basis == "kg" for item in page.observations for offer in item.offers)
    assert all(item.product.package is None for item in page.observations)


def test_complete_live_search_traverses_all_source_pages(settings):
    with create_client(settings) as client:
        requester = create_requester(client, settings)
        prepared = ADAPTER.prepare(requester, settings)
        pages = list(ADAPTER.search_pages(requester, prepared, None, "detergente"))
    assert len(pages) > 1
    assert not any(page.issues for page in pages)
    identities = [item.product.source_product_id for page in pages for item in page.observations]
    assert identities
    assert len(identities) == len(set(identities))
