"""Preserve public routes, portion prices and verified regular quantity-promotion prices."""

import pytest
from stores.conftest import FIXTURES

from inflacao_scrapers.hirota.values import product_path
from inflacao_scrapers.vtex.json import decode_response

from .test_parsing import parse


def regression_page():
    document = decode_response((FIXTURES / "hirota-regressions.json").read_bytes())
    return parse(document)


def test_public_punctuation_is_encoded_inside_the_product_slug():
    page = regression_page()
    assert not page.issues and len(page.observations) == 7
    paper = next(item for item in page.observations if item.product.source_product_id == "1886")
    assert "%C2%A0" in paper.product_url
    container = next(item for item in page.observations if item.product.source_product_id == "7657")
    assert container.product_url.endswith("capac%3A330")


def test_unit_portions_do_not_become_kilogram_prices_or_fixed_packages():
    page = regression_page()
    portion = next(item for item in page.observations if item.product.source_product_id == "7178")
    assert portion.offers[0].amount == "34.90" and portion.offers[0].basis == "package"
    assert portion.product.package is None
    assert "porção" in portion.offers[0].conditions.description
    fixed = next(item for item in page.observations if item.product.source_product_id == "1805")
    assert fixed.offers[0].amount == "25.98" and fixed.product.package.quantity == "1"


def test_quantity_promotion_keeps_regular_displayed_price_without_rounding_an_average():
    page = regression_page()
    item = next(item for item in page.observations if item.product.source_product_id == "12131")
    assert [offer.amount for offer in item.offers] == ["8.98"]
    assert item.offers[0].conditions.minimum_quantity is None
    assert '"quantidade_minima": 3' in item.offers[0].conditions.description
    assert any("quantity-promotion" in warning for warning in page.warnings)


def test_verified_package_tiers_keep_their_own_quantity_thresholds():
    page = regression_page()
    item = next(item for item in page.observations if item.product.source_product_id == "4989")
    assert [offer.amount for offer in item.offers] == ["19.98", "14.98"]
    assert [offer.conditions.minimum_quantity for offer in item.offers] == [None, "20"]
    assert '"faixas_precos"' in item.offers[1].conditions.description


@pytest.mark.parametrize("slug", ["../other", "a/b", "a?b", "a#b", "a%2fb", "a\\b", "a\nb"])
def test_slug_encoding_does_not_admit_paths_queries_or_control_characters(slug):
    with pytest.raises(ValueError):
        product_path({"produto_id": 1, "link": slug})
