"""Store-461 source formats captured from the production runtime on 2026-11-02."""

from datetime import UTC, datetime

import pytest

from inflacao_scrapers.pao_de_acucar.parsing import parse_products
from inflacao_scrapers.vtex.json import decode_response

from .test_source import FIXTURES, settings


def document():
    return decode_response((FIXTURES / "pao-de-acucar-regressions.json").read_bytes())


def parse_regressions(value=None):
    return parse_products(
        document() if value is None else value,
        settings(),
        "https://api.vendas.gpa.digital/pa/search/category-page",
        datetime(2026, 11, 2, 20, tzinfo=UTC),
        None,
    )


def test_regular_and_quantity_promotions_remain_separate():
    page = parse_regressions()
    assert not page.issues and len(page.observations) == 7
    items = {item.product.source_product_id: item for item in page.observations}
    quantity = items["2373133"].offers
    assert [offer.amount for offer in quantity] == ["6.99", "4.66"]
    assert [offer.conditions.minimum_quantity for offer in quantity] == [None, "3"]
    second = items["1136507"].offers
    assert [offer.amount for offer in second] == ["19.99", "12.99"]
    assert second[1].conditions.minimum_quantity == "2"
    assert all(offer.conditions.membership_required is None for offer in second)
    assert [offer.amount for offer in items["4423188"].offers] == ["2.32"]
    assert items["4423188"].offers[0].reference_amount == "3.09"


def test_weight_promotions_inherit_conditions_and_use_only_advertised_kg_prices():
    items = {item.product.source_product_id: item for item in parse_regressions().observations}
    salmon = items["0229210"]
    assert [offer.amount for offer in salmon.offers] == ["61.74"]
    assert all(offer.basis == "kg" for offer in salmon.offers)
    assert salmon.product.package is None
    assert "153467" in salmon.offers[0].conditions.description
    assert not items["0304863"].offers


def test_corrupt_reference_price_is_omitted_without_rounding_or_losing_selling_price():
    page = parse_regressions()
    item = next(item for item in page.observations if item.product.source_product_id == "9902512")
    assert item.offers[0].amount == "40.08" and item.offers[0].reference_amount is None
    assert any("reference-price" in warning for warning in page.warnings)


@pytest.mark.parametrize("field,value", [("paymentFormName", "Cartão"), ("appExclusive", True)])
def test_unknown_restrictions_cannot_become_ordinary_prices(field, value):
    source = document()
    product = source["products"][1]
    product["productPromotions"][0][field] = value
    product["productPromotion"][field] = value
    source["products"] = [product]
    page = parse_regressions(source)
    assert page.issues and not page.observations


def test_kg_promotion_without_matching_parent_does_not_lose_restrictions():
    source = document()
    product = next(item for item in source["products"] if item["sku"] == "0229210")
    product["productPromotions"] = []
    product["productPromotion"] = None
    source["products"] = [product]
    assert parse_regressions(source).issues


def test_item_quantity_is_never_relabelled_as_a_kg_threshold():
    source = document()
    product = next(item for item in source["products"] if item["sku"] == "0229210")
    product["productPromotions"][0].update(promotionQuantityBuy=3, promotionQuantityPayFor=2)
    product["productPromotion"].update(promotionQuantityBuy=3, promotionQuantityPayFor=2)
    source["products"] = [product]
    page = parse_regressions(source)
    assert not page.observations and "kg quantity threshold" in page.issues[0]
