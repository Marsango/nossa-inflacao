from datetime import UTC, datetime
from pathlib import Path

import pytest

from inflacao_scrapers.carrefour.config import CONTEXTS, CarrefourSettings
from inflacao_scrapers.carrefour.decoding import ReferenceTable
from inflacao_scrapers.vtex.json import decode_response

FIXTURES = Path(__file__).parents[1] / "fixtures/stores"
OBSERVED_AT = datetime(2026, 11, 3, 11, tzinfo=UTC)


def configuration(state="SP"):
    city, postal_code, region_id = CONTEXTS[state]
    return CarrefourSettings(
        scraper_id="authorized-collector",
        city=city,
        state=state,
        postal_code=postal_code,
        region_id=region_id,
        store_id=f"region:{region_id}/seller:1",
    )


def captured_search(state="SP"):
    return ReferenceTable((FIXTURES / f"carrefour-{state.lower()}.data").read_text()).route(
        "routes/busca.$term"
    )


def captured_weight(state="SP"):
    return decode_response((FIXTURES / f"carrefour-{state.lower()}-weight.json").read_bytes())


@pytest.fixture(params=["SP", "RJ"])
def settings(request):
    return configuration(request.param)


def encoded_table(document):
    import json

    entries = []
    add_reference(document, entries)
    return json.dumps(entries, default=str)


def add_reference(value, entries):
    reference = len(entries)
    entries.append(None)
    if isinstance(value, dict):
        entries[reference] = {
            "_" + str(add_reference(key, entries)): add_reference(item, entries)
            for key, item in value.items()
        }
        return reference
    if isinstance(value, list):
        entries[reference] = [add_reference(item, entries) for item in value]
        return reference
    entries[reference] = value
    return reference


def selected_region(settings):
    return {
        "regionId": settings.region_id,
        "postalCode": settings.postal_code,
        "regionContextProps": {
            "regionId": settings.region_id,
            "status": "loaded",
            "deliveryType": "residential",
            "deliveryAddress": settings.city,
        },
    }


def selected_storefront(settings):
    return {
        "regionId": settings.region_id,
        "postalCode": settings.postal_code,
        "deliveryType": "residential",
        "text": "Receber em: " + settings.city,
    }
