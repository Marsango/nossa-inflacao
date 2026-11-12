import base64
import json

import httpx
import pytest

from inflacao_scrapers.gbarbosa.config import GBarbosaSettings
from inflacao_scrapers.transport import Requester
from inflacao_scrapers.vtex.fetching import request_products
from inflacao_scrapers.vtex.regional import prepare_region

from .conftest import encode


def test_region_resolution_and_product_requests_retain_selected_context(capture, settings):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=encode(capture["regions"]))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        requester = Requester(client, interval=0)
        prepared = prepare_region(requester, settings)
        request_products(requester, prepared, query="arroz branco")
    assert requests[0].url.params["postalCode"] == settings.postal_code
    assert requests[1].url.params["regionId"] == prepared.region_id
    assert "arroz%20branco" in str(requests[1].url)
    segment = requests[1].headers["cookie"].removeprefix("vtex_segment=")
    assert json.loads(base64.b64decode(segment))["regionId"] == prepared.region_id
    assert all("authorization" not in request.headers for request in requests)


@pytest.mark.parametrize(
    "regions", [[], [{"id": "national", "sellers": [{"id": "gbarbosab101", "name": "national"}]}]]
)
def test_missing_local_grocery_seller_stops_before_prices(settings, regions):
    def handler(request):
        assert request.url.path.endswith("/regions")
        return httpx.Response(200, json=regions)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="seller absent"),
    ):
        prepare_region(Requester(client), settings)


def test_unsupported_geography_cannot_be_labeled_as_a_verified_city():
    with pytest.raises(ValueError, match="Unverified GBarbosa"):
        GBarbosaSettings(scraper_id="test", city="Fortaleza", state="CE")


def test_prices_cannot_be_fetched_before_resolving_the_cep(settings):
    with pytest.raises(ValueError, match="must be verified"):
        settings.source_headers()


def test_configured_geography_matches_the_retailers_postal_lookup(capture, settings):
    address = capture["postal_address"]
    assert address["postalCode"] == settings.postal_code
    assert address["city"] == settings.city
    assert address["state"] == settings.state
    assert address["street"]
