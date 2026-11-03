import json
from copy import deepcopy
from datetime import UTC, datetime

import httpx
import pytest

from inflacao_scrapers.atacadao.parsing import parse_products
from inflacao_scrapers.atacadao.stock import stock_by_identity, with_availability
from inflacao_scrapers.scope import MonitoringTarget
from inflacao_scrapers.vtex.json import decode_response

from .conftest import FIXTURES, captured_products


def test_captured_stock_matches_the_same_seller_and_skus(settings):
    document = decode_response((FIXTURES / "atacadao-stock.json").read_bytes())
    rice = next(p for p in captured_products("rice") if p["sku"] == "13743")
    banana = captured_products("weight")[0]
    assert stock_by_identity(document, settings, [rice, banana]) == {
        "13743": "available",
        "41986": "available",
    }


@pytest.mark.parametrize("change", ["seller", "missing", "duplicate"])
def test_stock_cannot_fall_back_to_another_seller_or_omit_skus(settings, change):
    document = {
        "items": [{"id": "13743", "seller": settings.seller_id, "availability": "available"}]
    }
    if change == "seller":
        document["items"][0]["seller"] = "wrong-seller"
    if change == "missing":
        document["items"] = []
    if change == "duplicate":
        document["items"].append(deepcopy(document["items"][0]))
    product = next(p for p in captured_products("rice") if p["sku"] == "13743")
    with pytest.raises(ValueError, match="Atacadão stock"):
        stock_by_identity(document, settings, [product])


def test_stock_simulation_is_anonymous_and_does_not_replace_catalog_prices(settings):
    products = captured_products("rice")[:1]
    before = deepcopy(products)

    def respond(request):
        assert request.method == "POST" and request.url.path.endswith("/orderForms/simulation")
        assert "authorization" not in request.headers
        items = json.loads(request.content)["items"]
        assert items == [{"id": products[0]["sku"], "quantity": 1, "seller": settings.seller_id}]
        return httpx.Response(
            200, json={"items": [{**items[0], "availability": "withoutStock", "price": 1}]}
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        checked = with_availability(client, settings, products)
    assert checked[0]["availability"] == "withoutStock"
    assert checked[0]["offers"] == before[0]["offers"]
    assert products == before


def test_description_matches_do_not_expand_the_core_monitoring_scope(settings):
    rice = next(p for p in captured_products("rice") if p["sku"] == "13743")
    pet = {
        **deepcopy(rice),
        "id": "40008",
        "sku": "40008",
        "name": "Alimento para Cães Arroz e Carne 15kg",
    }
    target = rice_target()
    with httpx.Client(transport=httpx.MockTransport(rice_stock_response)) as client:
        products = with_availability(client, settings, [rice, pet], target)
    parsed = parse_products(products, settings, settings.shop_url, datetime.now(UTC), target)
    assert not parsed.issues
    assert [o.product.source_product_id for o in parsed.observations] == ["13743"]


def rice_target():
    return MonitoringTarget(
        id="rice",
        name="Rice",
        search_queries=["arroz"],
        required_terms=[["arroz"], ["branco"], ["tipo 1"]],
        excluded_terms=[],
    )


def rice_stock_response(request):
    items = json.loads(request.content)["items"]
    assert [item["id"] for item in items] == ["13743"]
    return httpx.Response(200, json={"items": [{**items[0], "availability": "available"}]})
