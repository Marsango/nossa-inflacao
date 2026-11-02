"""Exact source values; unknown values and internal barcodes stay unknown."""

from decimal import Decimal
from urllib.parse import quote

from ..models.product import validate_gtin


def source_money(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("Invalid exact monetary value")
    number = Decimal(value)
    if not number.is_finite() or number < 0 or number != number.quantize(Decimal("0.01")):
        raise ValueError("Invalid monetary precision or amount")
    if number == 0:
        return None
    return format(number, ".2f")


def source_gtin(value) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        validate_gtin(value)
    except ValueError:
        return None
    return value


def product_identity(product) -> str:
    if not isinstance(product, dict):
        raise ValueError("Malformed Hirota product")
    identity = product["produto_id"]
    if type(identity) is not int or identity <= 0:
        raise ValueError("Invalid public product identity")
    return str(identity)


def product_path(product) -> str:
    slug = product["link"]
    if not isinstance(slug, str) or not slug.strip() or slug in {".", ".."}:
        raise ValueError("Invalid public product link")
    if any(character in slug for character in "/\\?#%") or any(
        ord(c) < 32 or ord(c) == 127 for c in slug
    ):
        raise ValueError("Invalid public product link")
    return "/produto/" + product_identity(product) + "/" + quote(slug, safe="-")
