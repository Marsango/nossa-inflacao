"""Keep regular and wholesale offers separate, with explicit purchase thresholds."""

import json

from ..models import Conditions, Offer
from .values import minimum_quantity, positive_quantity, price, sale_basis


def product_offers(product, settings):
    basis, portion = sale_basis(product)
    summary = product.get("offers")
    if not isinstance(summary, dict) or not isinstance(summary.get("offers"), list):
        raise ValueError("Atacadão offers missing")
    if len(summary["offers"]) > 20:
        raise ValueError("Atacadão offer limit exceeded")
    description = conditions_description(product, basis)
    return [
        source_offer(entry, settings, basis, portion, description) for entry in summary["offers"]
    ]


def source_offer(source, settings, basis, portion, description):
    if source["seller"]["identifier"] != settings.seller_id:
        raise ValueError("Atacadão offer seller does not match verified branch")
    if positive_quantity(source.get("quantity")) != 1:
        raise ValueError("Unverified Atacadão offer quantity")
    amount = price(source.get("price"))
    reference = source.get("listPrice")
    if reference is not None:
        reference = price(reference)
    return Offer(
        amount=amount,
        currency="BRL",
        basis=basis,
        reference_amount=reference,
        conditions=offer_conditions(source, basis, portion, description),
    )


def conditions_description(product, basis):
    description = "Atacadão online branch catalog; payment, membership and coupon terms unknown."
    if basis == "kg":
        description += (
            " Advertised per-kg price; unitMultiplier is an approximate purchase portion."
        )
    details = promotion_details(product)
    if details:
        description += " Source conditions: " + json.dumps(details, ensure_ascii=False, default=str)
    return description


def promotion_details(product):
    highlights = [
        seller["commertialOffer"].get("discountHighlights") for seller in product.get("sellers", [])
    ]
    details = {
        "discountHighlights": list(filter(None, highlights)),
        "precoExclusivoEcom": product["offers"].get("precoExclusivoEcom"),
    }
    return {key: value for key, value in details.items() if value}


def offer_conditions(source, basis, portion, description):
    return Conditions(
        payment_method="unknown",
        installments=None,
        membership_required=None,
        membership_program=None,
        coupon_required=None,
        minimum_quantity=minimum_quantity(source, basis, portion),
        description=description,
    )
