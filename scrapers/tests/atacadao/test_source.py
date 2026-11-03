import json
from copy import deepcopy
from functools import partial

import httpx
import pytest

from inflacao_scrapers.atacadao.source import (
    branch_document,
    fetch_products,
    prepare_context,
    request_source,
    validate_branch,
    validate_catalog_context,
    validate_directory,
)

from .conftest import configuration


def branch_html(branch):
    document = {"props": {"pageProps": {"storeInfo": branch}}}
    return (
        '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(document) + "</script>"
    )


def test_every_capital_requires_independent_directory_and_branch(capital):
    settings = configuration(capital)
    requests = []
    respond = partial(capital_response, capital=capital, requests=requests)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        prepared = prepare_context(client, settings)
    prepared.require_context()
    with pytest.raises(ValueError, match="verified"):
        settings.require_context()
    assert requests[0].url.params["accountName"] == settings.seller_id
    assert requests[1].url.path == "/loja/" + settings.branch_slug
    assert all("authorization" not in request.headers for request in requests)


def capital_response(request, capital, requests):
    requests.append(request)
    if request.url.host.startswith("bff-"):
        return httpx.Response(200, content=json.dumps(capital["directory"], default=str).encode())
    if request.url.path.endswith("graphql"):
        document = deepcopy(capital["catalog"])
        products = document["data"]["search"]["products"]
        products["edges"] = products["edges"][:1]
        return httpx.Response(200, content=json.dumps(document, default=str).encode())
    return httpx.Response(200, text=branch_html(capital["branch"]))


@pytest.mark.parametrize(
    "field,value",
    [
        ("storeId", -1),
        ("accountName", "wrong-seller"),
        ("city", "Wrong city"),
        ("uf", "XX"),
        ("postalCode", "00000-000"),
        ("slug", "wrong-branch"),
    ],
)
def test_changed_branch_cannot_assign_prices_to_a_city(capital, field, value):
    capital["branch"][field] = value
    with pytest.raises(ValueError, match="Atacadão"):
        validate_branch(capital["branch"], configuration(capital))


def test_directory_rejects_missing_duplicate_and_different_city(capital):
    settings = configuration(capital)
    with pytest.raises(ValueError, match="missing"):
        validate_directory([], settings)
    duplicate = capital["directory"] + deepcopy(capital["directory"])
    with pytest.raises(ValueError, match="ambiguous"):
        validate_directory(duplicate, settings)
    capital["directory"][0]["city"] = "Wrong city"
    with pytest.raises(ValueError, match="city changed"):
        validate_directory(capital["directory"], settings)


def test_legacy_postal_code_does_not_override_current_address(capital):
    capital["branch"]["cep"] = "00000-000"
    validate_branch(capital["branch"], configuration(capital))


@pytest.mark.parametrize("status,headers", [(403, {}), (429, {}), (200, {"Age": "20"})])
def test_denied_or_aged_source_is_not_an_empty_success(status, headers):
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, headers=headers))
    ) as client:
        with pytest.raises(ValueError, match="Atacadão"):
            request_source(client, "https://www.atacadao.com.br/api/graphql")


def test_block_html_and_duplicate_storefront_data_fail():
    with pytest.raises(ValueError, match="blocked"):
        branch_document(b"<html>Sorry, you have been blocked</html>")
    with pytest.raises(ValueError):
        branch_document((branch_html({}) * 2).encode())


def test_empty_catalog_and_seller_fallback_are_blockers(settings):
    with pytest.raises(ValueError, match="empty"):
        validate_catalog_context({"pageInfo": {"totalCount": 0}, "edges": []}, settings)
    product = {"offers": {"offers": [{"seller": {"identifier": "other-store"}}]}}
    document = {"pageInfo": {"totalCount": 1}, "edges": [{"node": product}]}
    with pytest.raises(ValueError, match="seller"):
        validate_catalog_context(document, settings)


def test_query_binds_each_page_to_seller_and_uses_fresh_url(settings):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"data": {"search": {"products": {}}}})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        fetch_products(client, settings, "arroz", 50, 50)
        fetch_products(client, settings, "arroz", 50, 50)
    parameters = requests[0].url.params
    variables = json.loads(parameters["variables"])
    selected = next(f for f in variables["selectedFacets"] if f["key"] == "channel")
    assert json.loads(selected["value"])["seller"] == settings.seller_id
    assert variables["after"] == "50" and variables["first"] == 50
    assert parameters["_ir"] != requests[1].url.params["_ir"]
