"""Exact values; internal Atacadão reference codes are not asserted to be GTINs."""

from decimal import Decimal

from ..packaging.resolution import canonical_quantity
from ..vtex.prices import decimal_value, money


def positive_quantity(value):
    quantity = decimal_value(value)
    if quantity <= 0:
        raise ValueError("Atacadão quantity must be positive")
    return quantity


def sale_basis(product):
    unit = product.get("measurementUnit")
    portion = positive_quantity(product.get("unitMultiplier"))
    if unit == "kg":
        return "kg", portion
    if unit == "un" and portion == 1:
        return "package", portion
    raise ValueError("Unverified Atacadão measurement unit or portion")


def minimum_quantity(source, basis, portion):
    minimum = positive_quantity(source.get("minQuantity"))
    if minimum != minimum.to_integral_value():
        raise ValueError("Atacadão minimum purchase count is not integral")
    if basis == "kg":
        return canonical_quantity(minimum * portion)
    return canonical_quantity(minimum)


def price(value):
    amount = money(value)
    if Decimal(amount) == 0:
        raise ValueError("Unexplained Atacadão zero price")
    return amount
