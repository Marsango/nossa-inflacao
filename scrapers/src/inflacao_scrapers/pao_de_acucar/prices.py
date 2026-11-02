"""Exact selling prices; unverifiable reference metadata stays unknown."""

from decimal import Decimal


def source_money(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise ValueError("Invalid exact GPA price")
    amount = Decimal(value)
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Invalid GPA money precision/range")
    if amount == 0:
        return None
    return format(amount, ".2f")


def reference_amount(value, amount, warnings):
    try:
        return validated_reference(value, amount)
    except (ValueError, ArithmeticError) as error:
        warnings.append(f"reference-price: omitted invalid reference ({error})")
        return None


def validated_reference(value, amount):
    reference = source_money(value)
    if reference is not None and Decimal(reference) < Decimal(amount):
        raise ValueError("reference is lower than selling price")
    return reference


def price_details(product):
    if product.get("variableWeight") is False:
        return product, "package"
    if product.get("variableWeight") is not True:
        raise ValueError("Unsupported GPA variable-weight portion or missing sale basis")
    details = product.get("variableWeightPrice")
    if details is None:
        return None, "kg"
    if not isinstance(details, dict):
        raise ValueError("Malformed GPA variable-weight price")
    return details, "kg"
