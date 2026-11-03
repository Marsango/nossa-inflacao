from copy import deepcopy
from pathlib import Path

import pytest

from inflacao_scrapers.carrefour.config import CONTEXTS, CarrefourSettings
from inflacao_scrapers.carrefour.parsing import parse_products
from inflacao_scrapers.carrefour.session import regional_selection, validate_selection
from inflacao_scrapers.config import load_configurations
from inflacao_scrapers.vtex.json import decode_response

from .conftest import FIXTURES, OBSERVED_AT, configuration, encoded_table

CAPITALS = decode_response((FIXTURES / "carrefour-capitals.json").read_bytes())
BLOCKERS = decode_response((FIXTURES / "carrefour-capital-blockers.json").read_bytes())


@pytest.mark.parametrize("capital", CAPITALS, ids=lambda capital: capital["state"])
def test_captured_capital_has_verified_selection_and_contract_prices(capital):
    settings = configuration(capital["state"])
    validate_selection(capital["selection"], settings)
    parsed = parse_products(capital["products"], settings, settings.shop_url, OBSERVED_AT)
    assert not parsed.issues and parsed.observations
    assert any(item.availability == "in_stock" and item.offers for item in parsed.observations)
    for observation in parsed.observations:
        assert observation.context.state == capital["state"]
        assert observation.context.city == capital["city"]
        assert observation.context.postal_code == capital["postal_code"]
        assert capital["selection"]["regionId"] in observation.context.store_id


def unavailable_product():
    capital = next(capital for capital in CAPITALS if capital["state"] == "RS")
    return next(
        product for product in capital["products"] if product["items"][0]["bestSeller"] is None
    )


def test_actual_unavailable_item_preserves_price_and_unknown_seller_id():
    settings = configuration("RS")
    parsed = parse_products([unavailable_product()], settings, settings.shop_url, OBSERVED_AT)
    assert not parsed.issues and len(parsed.observations) == 1
    observation = parsed.observations[0]
    assert observation.availability == "out_of_stock"
    assert observation.context.seller_id is None
    assert observation.offers[0].amount == "22.59"
    assert observation.product.source_product_id == "93"


@pytest.mark.parametrize("change", ["stock", "seller", "ambiguous"])
def test_missing_selected_seller_never_falls_back_to_an_available_or_other_seller(change):
    product = deepcopy(unavailable_product())
    item = product["items"][0]
    mutate_unavailable(item, change)
    settings = configuration("RS")
    parsed = parse_products([product], settings, settings.shop_url, OBSERVED_AT)
    assert parsed.issues and not parsed.observations


def mutate_unavailable(item, change):
    if change == "stock":
        item["sellers"][0]["commertialOffer"]["AvailableQuantity"] = 1
    if change == "seller":
        item["sellers"][0]["sellerId"] = "another-seller"
    if change == "ambiguous":
        item["sellers"].append(deepcopy(item["sellers"][0]))


def test_all_ready_cities_are_enabled_with_stable_ids_identity_and_separate_spools():
    path = Path(__file__).parents[2] / "scrapers.example.toml"
    all_settings = load_configurations(path)
    selected = [settings for settings in all_settings if settings.adapter == "carrefour"]
    assert {settings.state for settings in selected} == set(CONTEXTS) - {"RS"}
    assert len(selected) == 13 and all(settings.enabled for settings in selected)
    assert len({settings.schedule_id for settings in selected}) == 13
    assert len({settings.spool_path for settings in all_settings}) == len(all_settings)
    assert {settings.scraper_id for settings in all_settings} == {"muffato-curitiba-01"}


@pytest.mark.parametrize(
    "state", ["AC", "AL", "AP", "BA", "CE", "MA", "MT", "PA", "PI", "RO", "RR", "SE", "TO"]
)
def test_unverified_capitals_are_rejected_instead_of_using_default_prices(state):
    with pytest.raises(ValueError, match="Unverified Carrefour capital"):
        CarrefourSettings(scraper_id="collector", state=state)


def test_vitoria_destination_cannot_be_replaced_with_neighboring_vila_velha():
    settings = configuration("ES").model_dump()
    settings["city"] = "Vila Velha"
    with pytest.raises(ValueError, match="Unverified"):
        CarrefourSettings.model_validate(settings)


@pytest.mark.parametrize("blocker", BLOCKERS, ids=lambda blocker: blocker["state"])
def test_real_unsupported_cep_response_cannot_start_default_region_collection(blocker):
    assert blocker["status"] == 200
    assert blocker["response"]["data"]["error"]["status"] == 404
    assert blocker["region"] is None
    with pytest.raises(ValueError, match="did not resolve a store"):
        regional_selection(encoded_table(blocker["response"]))


def test_porto_alegre_mapping_is_retained_for_diagnostics_but_not_scheduled():
    settings = configuration("RS")
    path = Path(__file__).parents[2] / "scrapers.example.toml"
    configured = load_configurations(path)
    assert settings.city == "Porto Alegre"
    assert not any(entry.adapter == "carrefour" and entry.state == "RS" for entry in configured)
