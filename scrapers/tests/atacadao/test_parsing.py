from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from inflacao_scrapers.atacadao.parsing import parse_products
from inflacao_scrapers.models.validation import validate_wire

from .conftest import captured_products, configuration


def parse(products, settings):
    return parse_products(products, settings, settings.shop_url, datetime.now(UTC))


def test_every_verified_capital_retains_its_branch_and_geography(capital):
    settings = configuration(capital)
    settings.verify_context()
    products = [e["node"] for e in capital["catalog"]["data"]["search"]["products"]["edges"]]
    page = parse(products, settings)
    assert page.observations and not page.issues
    for observation in page.observations:
        assert observation.context.city == settings.city
        assert observation.context.state == settings.state
        assert observation.context.store_id == settings.store_id
        assert observation.context.seller_id == settings.seller_id
        assert observation.context.channel == "online"
        assert observation.context.postal_code is None
        validate_wire(observation.model_dump(mode="json"), "observation")


def test_regular_and_quantity_discount_are_separate_offers(settings):
    products = captured_products("rice")
    product = next(p for p in products if p["sku"] == "13743")
    observation = parse([product], settings).observations[0]
    assert observation.product.package.quantity == "5"
    assert observation.product.package.count == 1
    assert observation.product.gtin is None
    assert [(o.amount, o.conditions.minimum_quantity) for o in observation.offers] == [
        ("23.49", "1"),
        ("22.99", "6"),
    ]
    assert observation.offers[1].reference_amount != "23.49"
    assert observation.availability == "unknown"
    assert all(o.conditions.membership_required is None for o in observation.offers)


def test_kilogram_price_is_not_an_estimated_portion_total(settings):
    product = captured_products("weight")[0]
    assert product["unitMultiplier"] == Decimal("0.15")
    observation = parse([product], settings).observations[0]
    assert observation.product.package is None
    assert observation.offers[0].basis == "kg"
    assert observation.offers[0].amount == "10.90"
    assert observation.offers[0].conditions.minimum_quantity == "0.15"


@pytest.mark.parametrize("value", [None, Decimal("0"), Decimal("-1"), Decimal("1.001"), True])
def test_unknown_or_invalid_price_never_becomes_zero(settings, value):
    product = captured_products("rice")[0]
    product["offers"]["offers"][0]["price"] = value
    page = parse([product], settings)
    assert page.issues and not page.observations


@pytest.mark.parametrize(
    "field,value", [("seller", {"identifier": "other-store"}), ("quantity", 6), ("minQuantity", 0)]
)
def test_unsupported_offer_cannot_lose_its_conditions(settings, field, value):
    product = captured_products("rice")[0]
    product["offers"]["offers"][0][field] = value
    page = parse([product], settings)
    assert page.issues and not page.observations


def test_missing_offers_and_explicit_out_of_stock_are_preserved(settings):
    product = captured_products("rice")[0]
    product["offers"]["offers"] = []
    product["availability"] = "https://schema.org/OutOfStock"
    observation = parse([product], settings).observations[0]
    assert observation.offers == [] and observation.availability == "out_of_stock"


def test_source_promotion_restrictions_survive_without_guessing_payment_terms(settings):
    product = captured_products("rice")[0]
    product["sellers"][0]["commertialOffer"]["discountHighlights"] = [
        {"description": "Somente cartão Atacadão"}
    ]
    product["offers"]["precoExclusivoEcom"] = True
    conditions = parse([product], settings).observations[0].offers[0].conditions
    assert "Somente cartão Atacadão" in conditions.description
    assert '"precoExclusivoEcom": true' in conditions.description
    assert conditions.payment_method == "unknown"


def test_wrong_identity_url_and_sale_basis_are_reported_individually(settings):
    original = captured_products("rice")[0]
    products = [deepcopy(original) for _ in range(3)]
    products[0]["sku"] = "wrong"
    products[1]["slug"] = "https://other.example/product"
    products[2]["measurementUnit"] = "unknown"
    page = parse(products, settings)
    assert len(page.issues) == 3 and not page.observations
