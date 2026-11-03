"""Opt-in, read-only diagnostics; never ingest live data."""

import pytest

from inflacao_scrapers.commands import create_client, create_requester
from inflacao_scrapers.config import load_configurations
from inflacao_scrapers.pao_de_acucar.adapter import ADAPTER
from inflacao_scrapers.pao_de_acucar.catalog import fetch_page, validate_page
from inflacao_scrapers.pao_de_acucar.config import PaoDeAcucarSettings
from inflacao_scrapers.pao_de_acucar.parsing import parse_products

from .test_source import FIXTURES


@pytest.mark.live
@pytest.mark.parametrize("query,basis", [("arroz", "package"), ("melão", "kg")])
def test_live_delivery_discovery(query, basis):
    settings = PaoDeAcucarSettings(scraper_id="diagnostic-sp")
    with create_client(settings) as client:
        requester = create_requester(client, settings)
        prepared = ADAPTER.prepare(requester, settings)
        page = ADAPTER.discover(requester, prepared, query, 1)
    assert not page.issues and len(page.observations) == 1
    observation = page.observations[0]
    assert observation.context.store_id == "461"
    assert observation.context.postal_code == "04115090"
    assert observation.offers[0].basis == basis


def capital_settings():
    template = FIXTURES.parents[2] / "scrapers.example.toml"
    return [settings for settings in load_configurations(template)
            if settings.adapter == "pao-de-acucar" and settings.schedule_id is not None]


@pytest.mark.live
@pytest.mark.parametrize("settings", capital_settings(), ids=lambda settings: settings.state)
def test_live_capital_delivery_catalog(settings):
    from datetime import UTC, datetime

    with create_client(settings) as client:
        requester = create_requester(client, settings)
        prepared = ADAPTER.prepare(requester, settings)
        document, url = fetch_page(requester, prepared, "alimentos", 1)
    validate_page(document, 1, set(), None)
    page = parse_products(document, prepared, url, datetime.now(UTC), None)
    assert not page.issues and len(page.observations) == 12
    assert any(observation.offers for observation in page.observations)
    assert {observation.context.state for observation in page.observations} == {settings.state}
