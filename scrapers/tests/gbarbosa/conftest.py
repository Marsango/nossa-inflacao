import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from inflacao_scrapers.gbarbosa.config import GBarbosaSettings
from inflacao_scrapers.vtex.json import decode_response
from inflacao_scrapers.vtex.parsing import parse_products

FIXTURES = Path(__file__).parents[1] / "fixtures/stores"


@pytest.fixture(params=["se", "ba", "al"])
def capture(request):
    return decode_response((FIXTURES / f"gbarbosa-{request.param}.json").read_bytes())


def configuration(capture):
    fields = ("postal_code", "regional_seller_id", "city", "state")
    return GBarbosaSettings(scraper_id="shared-collector", **{key: capture[key] for key in fields})


@pytest.fixture
def settings(capture):
    return configuration(capture)


@pytest.fixture
def prepared(settings, capture):
    region = capture["regions"][0]["id"]
    return settings.model_copy(
        update={
            "region_id": region,
            "store_id": f"region:{region}/seller:{settings.regional_seller_id}",
        }
    )


def encode(document):
    return json.dumps(document, ensure_ascii=False, default=str).encode()


def parse(raw, settings):
    return parse_products(
        raw,
        settings=settings,
        source_url=settings.shop_url + "/api/catalog_system/pub/products/search",
        observed_at=datetime(2026, 11, 11, 20, tzinfo=UTC),
    )


def selected_product(capture, identity="13504"):
    return next(
        product for product in capture["products"] if product["items"][0]["itemId"] == identity
    )
