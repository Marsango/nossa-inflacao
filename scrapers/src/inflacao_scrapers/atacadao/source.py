"""Public storefront requests, exact JSON and independently checked branch identity."""

import base64
import json
import re
from uuid import uuid4

from ..scope import normalize
from ..vtex.json import decode_response

STORE_DIRECTORY = "https://bff-frontend-api.cloud.carrefour.com.br/api/v1/store-info"


def request_source(requester, url, parameters=None):
    response = requester.request(
        "GET",
        url,
        params=parameters,
        headers={"Cache-Control": "no-cache, max-age=0", "Pragma": "no-cache"},
    )
    validate_response(response)
    return response


def validate_response(response):
    if response.status_code != 200:
        raise ValueError(f"Atacadão HTTP {response.status_code}; collection incomplete")
    if int(response.headers.get("Age", "0")) > 0:
        raise ValueError("Atacadão aged cached response; collection incomplete")


def branch_document(raw):
    source = raw.decode("utf-8")
    matches = re.findall(r'<script\b[^>]*\bid="__NEXT_DATA__"[^>]*>(.*?)</script>', source, re.S)
    if len(matches) != 1:
        raise ValueError("Atacadão storefront data absent; possible blocked response")
    document = decode_response(matches[0].encode())
    return document["props"]["pageProps"]["storeInfo"]


def prepare_context(requester, settings):
    print(
        f"shop=atacadao schedule_id={settings.schedule_id} city={settings.city} "
        f"state={settings.state} store_id={settings.store_id} preparing",
        flush=True,
    )
    response = request_source(
        requester, STORE_DIRECTORY, {"accountName": settings.seller_id, "type": "loja"}
    )
    validate_directory(decode_response(response.content), settings)
    response = request_source(requester, settings.shop_url + "/loja/" + settings.branch_slug)
    validate_branch(branch_document(response.content), settings)
    prepared = settings.model_copy(deep=True)
    prepared.verify_context()
    document, _ = fetch_products(requester, prepared, "", 0, 1)
    validate_catalog_context(document, prepared)
    return prepared


def validate_catalog_context(document, settings):
    total = document["pageInfo"]["totalCount"]
    edges = document.get("edges")
    if type(total) is not int or total <= 0 or not isinstance(edges, list) or len(edges) != 1:
        raise ValueError("Atacadão branch catalog empty or malformed; collection not started")
    offers = edges[0]["node"]["offers"]["offers"]
    if not offers or any(offer["seller"]["identifier"] != settings.seller_id for offer in offers):
        raise ValueError("Atacadão catalog seller does not match configured branch")


def validate_directory(document, settings):
    if not isinstance(document, list):
        raise ValueError("Atacadão branch directory malformed")
    matches = [entry for entry in document if entry.get("accountName") == settings.seller_id]
    if len(matches) != 1:
        raise ValueError("Atacadão branch missing or ambiguous in public directory")
    entry = matches[0]
    if entry.get("slug") != settings.branch_slug:
        raise ValueError("Atacadão branch slug changed")
    validate_address(entry.get("city"), entry.get("uf"), entry.get("postalCode"), settings)


def validate_branch(branch, settings):
    expected = {
        "storeId": int(settings.store_id),
        "slug": settings.branch_slug,
        "accountName": settings.seller_id,
        "loja": settings.branch_name,
    }
    if not isinstance(branch, dict) or any(
        branch.get(key) != value for key, value in expected.items()
    ):
        raise ValueError("Atacadão branch identity changed")
    extras = branch.get("extras") or {}
    if extras.get("extra01") not in (None, settings.seller_id):
        raise ValueError("Atacadão branch seller mapping changed")
    validate_address(branch.get("city"), branch.get("uf"), branch.get("postalCode"), settings)
    if normalize(branch.get("cidade", "")) != normalize(settings.city):
        raise ValueError("Atacadão physical branch city changed")


def validate_address(city, state, postal_code, settings):
    if not isinstance(city, str) or normalize(city) != normalize(settings.city):
        raise ValueError("Atacadão branch city changed")
    if state != settings.state or not isinstance(postal_code, str):
        raise ValueError("Atacadão branch address changed")
    if postal_code.replace("-", "") != settings.branch_postal_code:
        raise ValueError("Atacadão branch postal code changed")


def channel(settings):
    region = base64.b64encode(("SW#" + settings.seller_id).encode()).decode()
    return json.dumps(
        {"salesChannel": settings.sales_channel, "seller": settings.seller_id, "regionId": region},
        separators=(",", ":"),
    )


def search_variables(settings, query, offset, limit):
    return {
        "first": limit,
        "after": str(offset),
        "sort": "name_asc",
        "term": query,
        "selectedFacets": [
            {"key": "channel", "value": channel(settings)},
            {"key": "locale", "value": "pt-BR"},
        ],
    }


def fetch_products(requester, settings, query, offset, limit):
    settings.require_context()
    response = request_source(
        requester,
        settings.shop_url + "/api/graphql",
        {
            "operationName": "ProductsQuery",
            "variables": json.dumps(search_variables(settings, query, offset, limit)),
            "_ir": str(uuid4()),
        },
    )
    document = decode_response(response.content)
    if not isinstance(document, dict) or document.get("errors"):
        raise ValueError("Atacadão catalog query failed")
    return document["data"]["search"]["products"], str(response.request.url)
