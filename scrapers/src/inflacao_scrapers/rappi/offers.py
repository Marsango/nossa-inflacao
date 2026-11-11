"""Parse fixed-package prices; preserve mandatory membership and unknown restrictions."""

from ..models import Conditions, Offer
from ..vtex.prices import decimal_value, money


def product_offers(source, storefront, warnings):
    if source.get("sale_type") != "U":
        warnings.append("Unverified weighted/portion sale type; price omitted")
        return []
    if restricted_discount(source):
        warnings.append("Unverified conditional/complex discount; price omitted")
        return []
    if source.get("price") is None:
        warnings.append("Missing Rappi price; never substituted with zero")
        return []
    amount = money(source["price"])
    if amount == "0.00":
        raise ValueError("Unexplained Rappi zero price")
    return [Offer(
        amount=amount, currency="BRL", basis="package",
        reference_amount=reference_price(source),
        conditions=offer_conditions(source, storefront),
    )]


def restricted_discount(source):
    discounts = source.get("discounts") or {}
    step = source.get("discount_step") or {}
    bundle = source.get("discounts_bundle") or {}
    flags = ("have_complex_discounts", "has_global_offers")
    values = ("discount_type", "discount_pay_products", "discount_earnings")
    if any(source.get(key) for key in flags + values):
        return True
    if any(discounts.get(key) for key in ("prime", "type", "pay_products", "earnings")):
        return True
    return any(step.values()) or any(bundle.values())


def reference_price(source):
    value = source.get("real_price")
    if value is None or decimal_value(value) == 0:
        return None
    return money(value)


def offer_conditions(source, storefront):
    minimum = minimum_quantity(source.get("min_purchasing_units"))
    membership = storefront.membership_required
    program = storefront.branch["name"] if membership else None
    return Conditions(
        payment_method="unknown", installments=None, membership_required=membership,
        membership_program=program, coupon_required=None, minimum_quantity=minimum,
        description=source_description(source),
    )


def minimum_quantity(value):
    if value is None:
        return None
    number = decimal_value(value)
    if number < 1 or number != number.to_integral_value():
        raise ValueError("Invalid Rappi minimum package quantity")
    return str(int(number))


def source_description(source):
    presentation = source.get("presentation") or "unknown"
    return (
        f"Rappi public preview; source presentation: {presentation}. "
        "Physical-store price equivalence, payment and coupon restrictions unverified."
    )
