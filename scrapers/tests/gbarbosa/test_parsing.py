from decimal import Decimal

import pytest

from inflacao_scrapers.vtex.json import decode_response

from .conftest import FIXTURES, encode, parse, selected_product


def test_captured_regional_prices_and_exact_money(prepared):
    raw = (FIXTURES / f"gbarbosa-{prepared.state.lower()}.json").read_bytes()
    page = parse(raw, prepared)
    assert not page.issues
    assert len(page.observations) == 22
    observations = {item.product.source_product_id: item for item in page.observations}
    expected = {"SE": "5.99", "BA": "6.59", "AL": "6.69"}
    rice = observations["13504"]
    assert rice.offers[0].amount == expected[prepared.state]
    assert rice.product.package.model_dump() == {"quantity": "1", "unit": "kg", "count": 1}
    assert rice.context.store_id == prepared.store_id
    assert rice.context.channel == "delivery"
    assert rice.context.postal_code == prepared.postal_code
    assert all(item.observed_at.tzinfo is not None for item in page.observations)


def test_source_json_prices_are_decoded_as_decimals(capture):
    product = selected_product(capture)
    source = product["items"][0]["sellers"][0]["commertialOffer"]
    assert isinstance(source["Price"], Decimal)


def test_api_prices_agree_with_independently_selected_storefront(prepared):
    evidence = decode_response((FIXTURES / "gbarbosa-storefront-verification.json").read_bytes())
    raw = (FIXTURES / f"gbarbosa-{prepared.state.lower()}.json").read_bytes()
    observations = {
        item.product.source_product_id: item for item in parse(raw, prepared).observations
    }
    checks = [item for item in evidence["checks"] if item["postal_code"] == prepared.postal_code]
    assert len(checks) == 3
    for check in checks:
        assert check["regional_seller_id"] == prepared.regional_seller_id
        offer = observations[check["source_product_id"]].offers[0]
        assert displayed_price(offer) in check["excerpt"].replace("\u00a0", " ")


def displayed_price(offer):
    price = "R$ " + offer.amount.replace(".", ",")
    if offer.basis == "kg":
        return price + "/kg"
    return price


def test_weight_prices_are_not_multiplied_by_approximate_portions(capture, prepared):
    products = [selected_product(capture, identity) for identity in ("6294", "12973")]
    page = parse(encode(products), prepared)
    assert not page.issues
    expected = {"SE": ["3.59", "45.79"], "BA": ["4.99", "39.99"], "AL": ["4.99", "39.99"]}
    assert [item.offers[0].amount for item in page.observations] == expected[prepared.state]
    assert all(item.product.package is None for item in page.observations)
    assert all(offer.basis == "kg" for item in page.observations for offer in item.offers)
    assert all(len(item.offers) == 1 for item in page.observations)
    assert all("payment-basis" in warning for warning in page.warnings)


def test_captured_unavailable_listings_have_no_zero_price(capture, prepared):
    page = parse(encode(capture), prepared)
    unavailable = [item for item in page.observations if item.availability == "out_of_stock"]
    assert unavailable
    assert all(item.offers == [] for item in unavailable)


def test_promotions_preserve_unknown_conditions(capture, prepared):
    product = selected_product(capture)
    source = product["items"][0]["sellers"][0]["commertialOffer"]
    source["Teasers"] = [{"name": "Clube GBarbosa: desconto na segunda unidade"}]
    page = parse(encode([product]), prepared)
    conditions = page.observations[0].offers[0].conditions
    assert "segunda unidade" in conditions.description
    assert conditions.membership_required is None
    assert conditions.coupon_required is None
    assert conditions.minimum_quantity is None


@pytest.mark.parametrize("price,available", [(None, True), (0, False)])
def test_missing_price_and_unavailable_zero_stay_unknown(capture, prepared, price, available):
    product = selected_product(capture)
    source = product["items"][0]["sellers"][0]["commertialOffer"]
    source.update(Price=price, IsAvailable=available)
    page = parse(encode([product]), prepared)
    assert not page.issues
    assert page.observations[0].offers == []


def test_unverified_large_weight_portions_are_explicit_issues(capture, prepared):
    product = selected_product(capture, "12973")
    product["items"][0]["unitMultiplier"] = "2"
    page = parse(encode([product]), prepared)
    assert not page.observations
    assert "unsupported unit multiplier" in page.issues[0]
