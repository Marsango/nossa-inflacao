"""Beira Mar API prices agree with independently rendered advertised kilogram prices."""
from datetime import UTC, datetime
from pathlib import Path

import pytest

from inflacao_scrapers.angeloni.categories import catalog_partitions
from inflacao_scrapers.angeloni.config import AngeloniSettings
from inflacao_scrapers.commands import create_client, create_requester
from inflacao_scrapers.vtex.catalog import request_catalog
from inflacao_scrapers.vtex.json import decode_response
from inflacao_scrapers.vtex.parsing import parse_products
from inflacao_scrapers.vtex.regional import prepare_region

FIXTURES = Path(__file__).parents[1] / "fixtures/stores"


def settings(**changes):
    values = dict(scraper_id="collector", postal_code="88015200", city="Florianópolis",
                  state="SC", regional_seller_id="superangeloni14",
                  store_id="region:verified/seller:superangeloni14", region_id="verified")
    return AngeloniSettings(**(values | changes))


@pytest.mark.parametrize("identity,amount", [("150177", "6.59"), ("4721796", "53.90"),
                                           ("58297", "17.99")])
def test_florianopolis_advertised_kilogram_prices(identity, amount):
    raw = (FIXTURES / "angeloni-florianopolis-weight.json").read_bytes()
    page = parse_products(raw, settings=settings(), source_url="https://super.angeloni.com.br",
                          observed_at=datetime.now(UTC), selected_sku=identity)
    assert not page.issues and len(page.observations) == 1
    observation = page.observations[0]
    assert observation.context.state == "SC" and observation.context.city == "Florianópolis"
    assert observation.context.postal_code == "88015200"
    assert observation.product.package is None and observation.product.gtin is None
    assert observation.offers[0].basis == "kg" and observation.offers[0].amount == amount
    evidence = decode_response((FIXTURES / "angeloni-florianopolis-verification.json").read_bytes())
    assert any(identity in entry["text"] and entry["branch_verified"] for entry in evidence)


@pytest.mark.parametrize("changes", [{"regional_seller_id": "superangeloni21"},
                                     {"state": "PR"}, {"city": "Joinville"},
                                     {"sales_channel": "2"}, {"region_id": None}])
def test_unverified_contexts_cannot_reuse_florianopolis_weight_mapping(changes):
    assert not settings(**changes).supports_kilogram_prices()


@pytest.mark.live
@pytest.mark.parametrize("category,identity", [(183, "150177"), (84, "4721796"), (226, "58297")])
def test_live_florianopolis_kilogram_catalog(category, identity):
    configuration = settings(region_id=None, catalog_category_ids=[category])
    with create_client(configuration) as client:
        requester = create_requester(client, configuration)
        prepared = prepare_region(requester, configuration)
        partitions = catalog_partitions(requester, prepared)
        response = request_catalog(requester, prepared, 1, count=10, facet_path=partitions[0])
    page = parse_products(response.content, settings=prepared, source_url=str(response.url),
                          observed_at=datetime.now(UTC), selected_sku=identity)
    assert not page.issues and len(page.observations) == 1
    assert page.observations[0].offers[0].basis == "kg"
    assert page.observations[0].context.state == "SC"
