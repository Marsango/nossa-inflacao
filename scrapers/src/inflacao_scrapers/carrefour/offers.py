"""Keep regular, quantity and payment offers separate; never substitute a portion total."""

from ..models import Conditions, Offer
from ..vtex.offers import PAYMENT_METHODS
from ..vtex.prices import money
from .values import bulk_threshold, reference_price, regular_price

DESCRIPTION = "Carrefour delivery catalog; membership and coupon restrictions unknown."


def product_offers(item, seller):
    from .values import sale_basis

    basis = sale_basis(item)
    source = seller["commertialOffer"]
    amount = regular_price(source, basis)
    if amount is None:
        return []
    result = [offer(amount, basis, reference_price(source))]
    result.extend(bulk_offers(seller, basis))
    result.extend(payment_offers(seller, basis, amount))
    return list({entry.model_dump_json(): entry for entry in result}.values())


def offer(amount, basis, reference=None, minimum=None, method="unknown", count=None, detail=""):
    description = DESCRIPTION + " " + detail
    if basis == "kg":
        description += " Advertised per kg; approximate portion totals are not per-kg offers."
    return Offer(
        amount=amount,
        currency="BRL",
        basis=basis,
        reference_amount=reference,
        conditions=Conditions(
            payment_method=method,
            installments=count,
            membership_required=None,
            membership_program=None,
            coupon_required=None,
            minimum_quantity=minimum,
            description=description.strip(),
        ),
    )


def bulk_offers(seller, basis):
    bulk = seller.get("dualPrice")
    if not isinstance(bulk, dict) or type(bulk.get("enabled")) is not bool:
        raise ValueError("Carrefour bulk-price status absent or malformed")
    if not bulk["enabled"]:
        return []
    if basis != "package":
        raise ValueError("Carrefour weighted bulk price/minimum basis unverified")
    source = bulk["lowPrice"]
    minimum = bulk_threshold(source.get("minQuantity"))
    amount = money(source["price"])
    if amount == "0.00":
        raise ValueError("Carrefour unexplained zero bulk price")
    return [offer(amount, basis, minimum=minimum, detail=f"From {minimum} packages.")]


def payment_offers(seller, basis, regular):
    if basis == "kg":
        return []
    details = seller.get("commertialOfferDetails") or {}
    groups = details.get("installmentsGroup", [])
    if not isinstance(groups, list):
        raise ValueError("Carrefour payment terms malformed")
    return [entry for group in groups for entry in group_offers(group, regular)]


def group_offers(group, regular):
    options = group.get("installments")
    if not isinstance(options, list):
        raise ValueError("Carrefour installment list malformed")
    method = PAYMENT_METHODS.get(group.get("paymentSystemGroupName"), "other")
    return [
        payment_offer(option, method, group)
        for option in options
        if money(option["totalValuePlusInterestRate"]) != regular
    ]


def payment_offer(source, method, group):
    count = source.get("numberOfInstallments")
    if type(count) is not int or count < 1:
        raise ValueError("Carrefour installment count malformed")
    installments = count if method == "credit_card" else None
    detail = "Payment: " + str(group.get("paymentSystemName") or "unknown")
    return offer(
        money(source["totalValuePlusInterestRate"]),
        "package",
        method=method,
        count=installments,
        detail=detail,
    )
