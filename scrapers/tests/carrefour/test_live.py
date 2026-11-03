import os
from itertools import islice

import pytest

from inflacao_scrapers.carrefour.catalog import search_pages
from inflacao_scrapers.carrefour.config import CONTEXTS
from inflacao_scrapers.carrefour.session import open_session

from .conftest import configuration

pytestmark = pytest.mark.live


def runtime_settings(settings):
    executable = os.environ.get("CARREFOUR_CHROME_PATH")
    return settings.model_copy(
        update={"chrome_executable_path": executable, "timeout_seconds": 30.0}
    )


@pytest.mark.parametrize("state", [state for state in CONTEXTS if state != "RS"])
def test_capital_region_prices_pagination_and_kilogram_basis(state):
    settings = runtime_settings(configuration(state))
    with open_session(settings) as driver:
        rice = list(islice(search_pages(driver, settings, None, "arroz", [3]), 2))
        bananas = list(search_pages(driver, settings, None, "banana", [5]))
    assert len(rice) == 2 and not any(page.issues for page in rice + bananas)
    observations = [item for page in rice for item in page.observations]
    assert len({item.product.source_product_id for item in observations}) == len(observations)
    assert all(item.context.postal_code == settings.postal_code for item in observations)
    assert any(item.availability == "in_stock" and item.offers for item in observations)
    weighted = [
        item for page in bananas for item in page.observations if item.product.package is None
    ]
    assert weighted and all(offer.basis == "kg" for item in weighted for offer in item.offers)
