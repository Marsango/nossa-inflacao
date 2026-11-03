"""Conservative basis, identifiers and exact monetary interpretation."""

import re

from ..vtex.prices import decimal_value, money


def identity(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
        raise ValueError("Carrefour source product/SKU identity missing")
    return value


def sale_basis(item: dict) -> str:
    unit = item.get("measurementUnit")
    if unit == "un":
        return "package"
    if unit == "kg":
        return "kg"
    raise ValueError(f"Unverified Carrefour measurement unit: {unit!r}")


def stock(source: dict) -> str:
    quantity = source.get("AvailableQuantity")
    if quantity is None:
        return "unknown"
    available = decimal_value(quantity)
    if available == 0:
        return "out_of_stock"
    return "in_stock"


def select_seller(item: dict, expected_seller: str) -> dict:
    if "bestSeller" not in item:
        raise ValueError("Carrefour selected-seller field missing")
    seller = item["bestSeller"]
    if seller is None:
        return unavailable_seller(item.get("sellers"), expected_seller)
    if not isinstance(seller, dict) or seller.get("sellerId") != expected_seller:
        raise ValueError("Carrefour seller differs from configured seller")
    return seller


def unavailable_seller(sellers, expected_seller: str) -> dict:
    if not isinstance(sellers, list) or len(sellers) != 1:
        raise ValueError("Carrefour unavailable seller missing or ambiguous")
    seller = sellers[0]
    if not isinstance(seller, dict) or seller.get("sellerName") != "Carrefour":
        raise ValueError("Carrefour unavailable seller identity changed")
    if seller.get("sellerId") not in (None, expected_seller):
        raise ValueError("Carrefour unavailable seller differs from configured seller")
    if stock(seller.get("commertialOffer", {})) != "out_of_stock":
        raise ValueError("Carrefour missing selected seller without explicit no-stock evidence")
    return seller


def regular_price(source, basis):
    value = source.get("Price")
    if value is None or decimal_value(value) == 0:
        return absent_price(source)
    amount = money(value)
    calculated = source.get("calculatedPrice")
    if basis == "package" and calculated is not None and money(calculated) != amount:
        raise ValueError("Carrefour package/portion price mismatch; unverified sale format")
    return amount


def absent_price(source):
    if stock(source) == "out_of_stock":
        return None
    raise ValueError("Carrefour price missing or unexplained zero; never a free product")


def reference_price(source):
    value = source.get("ListPrice")
    if value is None:
        return None
    return money(value)


def bulk_threshold(value):
    quantity = decimal_value(value)
    if quantity <= 1 or quantity != quantity.to_integral_value():
        raise ValueError("Carrefour bulk threshold is not a count greater than one")
    return str(int(quantity))


def package_name(name):
    return re.sub(
        r"(\btipo\s+[123])\s+-\s+(?=\d+(?:[.,]\d+)?\s*(?:kg|g|ml|l)\b)", r"\1 ", name, flags=re.I
    )
