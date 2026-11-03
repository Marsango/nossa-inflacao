from copy import deepcopy
from decimal import Decimal

import pytest

from inflacao_scrapers.carrefour.parsing import parse_products
from inflacao_scrapers.scope import MonitoringTarget

from .conftest import OBSERVED_AT, captured_search, captured_weight


def parse(products, settings, target=None):
    return parse_products(
        products, settings, settings.shop_url + "/busca/arroz.data", OBSERVED_AT, target
    )


def test_real_capital_skus_keep_prices_packages_and_region(settings):
    products = captured_search(settings.state)["products"]
    result = parse(products, settings)
    assert not result.issues and len(result.observations) == 3
    first = result.observations[0]
    assert first.product.source_product_id == products[0]["items"][0]["itemId"]
    assert first.context.postal_code == settings.postal_code
    assert first.context.store_id == settings.store_id
    assert first.context.channel == "delivery" and first.collection_method == "browser"
    assert first.product.gtin is None and first.product.package is not None
    assert first.offers[0].amount == ("6.59" if settings.state == "SP" else "30.89")
    assert first.availability == "in_stock"


def test_bulk_threshold_and_regular_price_remain_independent(settings):
    result = parse(captured_search(settings.state)["products"], settings)
    offers = result.observations[-1].offers
    assert len(offers) == 2
    assert offers[0].conditions.minimum_quantity is None
    assert offers[1].conditions.minimum_quantity == "3"
    assert offers[1].amount == ("7.29" if settings.state == "SP" else "9.68")
    assert offers[1].conditions.membership_required is None


def test_weighted_source_price_is_kg_not_approximate_portion(settings):
    products = captured_weight(settings.state)
    result = parse(products, settings)
    assert not result.issues and result.observations
    first = result.observations[0]
    source = products[0]["items"][0]["bestSeller"]["commertialOffer"]
    assert first.product.package is None and len(first.offers) == 1
    assert first.offers[0].basis == "kg"
    assert Decimal(first.offers[0].amount) == source["Price"]
    assert source["Price"] != source["calculatedPrice"]
    assert first.offers[0].conditions.minimum_quantity is None


@pytest.mark.parametrize("value", [None, 0, True, float("inf")])
def test_missing_zero_nonfinite_or_float_prices_never_become_valid_offers(settings, value):
    products = captured_search(settings.state)["products"][:1]
    products[0]["items"][0]["bestSeller"]["commertialOffer"]["Price"] = value
    result = parse(products, settings)
    assert result.issues and not result.observations


def test_unavailable_product_does_not_get_a_manufactured_zero_price(settings):
    products = captured_search(settings.state)["products"][:1]
    source = products[0]["items"][0]["bestSeller"]["commertialOffer"]
    source.update(Price=0, AvailableQuantity=0)
    result = parse(products, settings)
    assert not result.issues
    assert result.observations[0].availability == "out_of_stock"
    assert result.observations[0].offers == []


def test_other_seller_and_unsupported_weighted_bulk_fail(settings):
    products = captured_weight(settings.state)
    products[0]["items"][0]["bestSeller"]["sellerId"] = "other"
    products[1]["items"][0]["bestSeller"]["dualPrice"] = {
        "enabled": True,
        "lowPrice": {"minQuantity": 2, "price": Decimal("1.99")},
    }
    result = parse(products, settings)
    assert len(result.issues) == 2 and not result.observations


def test_unrelated_search_hits_are_filtered_using_core_scope(settings):
    products = captured_search(settings.state)["products"]
    unrelated = deepcopy(products[0])
    unrelated["productName"] = "Panela de Arroz 110V"
    products.append(unrelated)
    target = MonitoringTarget(
        id="arroz",
        name="Arroz",
        search_queries=["arroz"],
        required_terms=[["arroz"]],
        excluded_terms=["panela"],
    )
    result = parse(products, settings, target)
    assert not result.issues and len(result.observations) == 3


def test_known_pix_discount_retains_payment_restriction(settings):
    products = captured_search(settings.state)["products"][:1]
    seller = products[0]["items"][0]["bestSeller"]
    seller["commertialOfferDetails"]["installmentsGroup"] = [
        {
            "paymentSystemName": "Pix",
            "paymentSystemGroupName": "instantPaymentPaymentGroup",
            "installments": [
                {"numberOfInstallments": 1, "totalValuePlusInterestRate": Decimal("1.01")}
            ],
        }
    ]
    result = parse(products, settings)
    assert not result.issues
    discounted = result.observations[0].offers[-1]
    assert discounted.amount == "1.01" and discounted.conditions.payment_method == "pix"
