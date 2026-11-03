"""Ordinary paced HTTP; no customer cookies, authentication or search routes."""

from unicodedata import combining, normalize

from ..vtex.json import decode_response
from .config import API_BASE


def request_document(requester, path, *, parameters=None, body=None):
    method = "GET" if body is None else "POST"
    arguments = {"params": parameters, "headers": {"Cache-Control": "no-cache"}}
    if body is not None:
        arguments["json"] = body
    response = requester.request(method, API_BASE + path, **arguments)
    if response.status_code != 200:
        raise ValueError(f"Pão de Açúcar HTTP {response.status_code}; collection stopped")
    document = decode_response(response.content)
    if not isinstance(document, dict) or document.get("error"):
        raise ValueError("Pão de Açúcar malformed/failed response")
    return document, str(response.request.url)


def prepare_context(requester, settings):
    document, _ = request_document(
        requester, "delivery-v2/ecom/deliveryOptions", parameters={"zipCode": settings.postal_code}
    )
    validate_delivery(document, settings)
    document, _ = request_document(requester, f"stores/{settings.store_id}/humanization")
    validate_branch(document.get("content"), settings)
    prepared = settings.model_copy(deep=True)
    prepared.verify_context()
    return prepared


def validate_delivery(document, settings):
    entries = document.get("deliveryTypes")
    if not isinstance(entries, list):
        raise ValueError("Missing Pão de Açúcar delivery mapping")
    matches = [
        entry for entry in entries
        if isinstance(entry, dict) and entry.get("storeid") == int(settings.store_id)
    ]
    if len(matches) != 1:
        raise ValueError("Pão de Açúcar configured delivery mapping missing or ambiguous")
    entry = matches[0]
    expected = {"typeid": settings.delivery_type_id, "storeName": settings.branch_name,
                "erpCode": settings.branch_name.split(" - ", 1)[0], "name": "ENTREGA EXPRESS"}
    if any(entry.get(key) != value for key, value in expected.items()):
        raise ValueError("Pão de Açúcar delivery modality changed")
    validate_delivery_address(entry.get("address"), settings)


def validate_delivery_address(address, settings):
    if not isinstance(address, dict):
        raise ValueError("Missing GPA delivery branch address")
    validate_city(address.get("city"), settings.city)
    expected = {"state": settings.state, "addressNumber": settings.branch_address_number}
    if any(address.get(key) != value for key, value in expected.items()):
        raise ValueError("Pão de Açúcar delivery branch address changed")
    validate_postal_code(address.get("zipCode"), settings.branch_postal_code)


def validate_branch(branch, settings):
    expected = {"id": int(settings.store_id), "name": settings.branch_name,
                "addressNumber": settings.branch_address_number}
    if not isinstance(branch, dict) or any(
        branch.get(key) != value for key, value in expected.items()
    ):
        raise ValueError("Pão de Açúcar configured branch address changed")
    validate_city(branch.get("city"), settings.city)
    validate_postal_code(branch.get("zip"), settings.branch_postal_code)


def validate_city(value, expected):
    if not isinstance(value, str) or normalized_city(value) != normalized_city(expected):
        raise ValueError("Pão de Açúcar branch address changed: city mismatch")


def normalized_city(value):
    decomposed = normalize("NFKD", value)
    unaccented = "".join(character for character in decomposed if not combining(character))
    trimmed = unaccented.strip()
    return trimmed.upper()


def validate_postal_code(value, expected):
    if not isinstance(value, str) or value.replace("-", "") != expected:
        raise ValueError("Pão de Açúcar branch address changed: postal code mismatch")
