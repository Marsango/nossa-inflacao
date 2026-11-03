"""Captured local branches must be verified before emitting city-specific prices."""
from copy import deepcopy
from datetime import UTC, datetime

import httpx
import pytest

from inflacao_scrapers.pao_de_acucar.config import PaoDeAcucarSettings
from inflacao_scrapers.pao_de_acucar.parsing import parse_products
from inflacao_scrapers.pao_de_acucar.source import (
    prepare_context,
    validate_branch,
    validate_delivery,
)
from inflacao_scrapers.vtex.json import decode_response

from .test_source import FIXTURES

CAPITALS = decode_response((FIXTURES / "pao-de-acucar-capitals.json").read_bytes())["contexts"]


@pytest.fixture(params=CAPITALS, ids=lambda item: item["settings"]["state"])
def capital(request):
    return deepcopy(request.param)


def configuration(capital):
    return PaoDeAcucarSettings(scraper_id="authorized-collector", **capital["settings"])


def test_resolves_delivery_and_branch_before_setting_context(capital):
    settings = configuration(capital)
    requests = []

    def respond(request):
        requests.append(request)
        name = "delivery" if request.url.path.endswith("deliveryOptions") else "branch"
        return httpx.Response(200, json=capital[name])

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        prepared = prepare_context(client, settings)
    prepared.require_context()
    with pytest.raises(ValueError, match="resolved"):
        settings.require_context()
    assert requests[0].url.params["zipCode"] == settings.postal_code
    assert requests[1].url.path.endswith(f"stores/{settings.store_id}/humanization")
    assert all("authorization" not in request.headers for request in requests)


def test_prices_keep_actual_city_branch_and_unknown_conditions(capital):
    settings = configuration(capital)
    settings.verify_context()
    page = parse_products(capital["catalog"], settings, settings.shop_url, datetime.now(UTC), None)
    assert not page.issues and page.observations
    observation = page.observations[0]
    assert observation.context.store_id == settings.store_id
    assert observation.context.postal_code == settings.postal_code
    assert observation.context.city == settings.city
    assert observation.context.state == settings.state
    assert observation.context.channel == "delivery"
    assert observation.offers and observation.offers[0].conditions.membership_required is None
    assert all("storeId=461" not in offer.conditions.description for offer in observation.offers)


@pytest.mark.parametrize("field,value", [("state", "SP"), ("city", "SAO PAULO"),
                                         ("zipCode", "04115-090"), ("addressNumber", 999999)])
def test_wrong_delivery_address_stops_collection(capital, field, value):
    capital["delivery"]["deliveryTypes"][0]["address"][field] = value
    with pytest.raises(ValueError, match="address changed"):
        validate_delivery(capital["delivery"], configuration(capital))


@pytest.mark.parametrize("field,value", [("id", 461), ("city", "SAO PAULO"),
                                         ("zip", "04115-090"), ("name", "1717 - Ricardo Jafet")])
def test_wrong_branch_identity_stops_collection(capital, field, value):
    capital["branch"]["content"][field] = value
    with pytest.raises(ValueError, match="address changed"):
        validate_branch(capital["branch"]["content"], configuration(capital))


def test_ambiguous_or_changed_delivery_mapping_stops_collection(capital):
    mapping = capital["delivery"]
    selected = mapping["deliveryTypes"][0]
    mapping["deliveryTypes"].append(deepcopy(selected))
    with pytest.raises(ValueError, match="ambiguous"):
        validate_delivery(mapping, configuration(capital))
    mapping["deliveryTypes"].pop()
    selected["typeid"] = 842
    with pytest.raises(ValueError, match="modality changed"):
        validate_delivery(mapping, configuration(capital))
