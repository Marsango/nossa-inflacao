"""Root product routes carry the same trusted host and source identity."""

from stores.conftest import FIXTURES

from inflacao_scrapers.nagumo.config import NagumoSettings
from inflacao_scrapers.vtex.json import decode_response

from .conftest import parse, source


def test_captured_root_routes_preserve_source_identity_and_prices():
    document = decode_response((FIXTURES / "nagumo-regressions.json").read_bytes())
    page = parse(document)
    assert not page.issues and len(page.observations) == 3
    oil = next(item for item in page.observations if item.product.source_product_id == "159623")
    assert oil.product_url.endswith("/%C3%B3leo-de-soja-liza-900-ml-159623.html")
    assert oil.offers[0].amount == "7.49"
    assert NagumoSettings(scraper_id="test").max_search_pages * 24 >= 2803


def test_ambiguous_package_metadata_does_not_discard_an_exact_price():
    document = source()
    document["productsSearchResult"][0]["productName"] = "Bebida proteica 15g 250ml"
    page = parse(document)
    assert not page.issues
    assert page.observations[0].product.package is None
    assert page.observations[0].offers[0].amount == "23.70"
    assert "package-size" in page.warnings[0]
