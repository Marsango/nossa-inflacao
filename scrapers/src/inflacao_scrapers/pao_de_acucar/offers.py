"""Keep regular, quantity and kilogram offers in their advertised bases."""

import json
from decimal import Decimal

from ..models import Conditions, Offer
from .prices import price_details as price_details
from .prices import reference_amount
from .prices import source_money as source_money
from .promotions import price_promotions, promotional_price


def product_offers(product, warnings):
    details, basis = price_details(product)
    if details is None:
        warnings.append("price-basis: advertised kg price missing; portion price omitted")
        return []
    amount = source_money(details.get("price"))
    if amount is None:
        return []
    reference = reference_amount(details.get("priceFrom"), amount, warnings)
    promotions = price_promotions(product, details)
    offers = [make_offer(product, details, amount, reference, basis)]
    promoted = list(promotional_offers(product, details, promotions, amount, basis))
    return selected_offers(offers, promoted)


def selected_offers(regular, promoted):
    if any(offer.conditions.minimum_quantity is None for offer in promoted):
        return promoted
    offers = regular + promoted
    return list({offer.model_dump_json(): offer for offer in offers}.values())


def promotional_offers(product, details, promotions, regular, basis):
    for promotion in promotions:
        yield from promotional_offer(product, details, promotion, regular, basis)


def promotional_offer(product, details, promotion, regular, basis):
    amount, quantity = promotional_price(promotion)
    if basis == "kg" and quantity is not None:
        raise ValueError("GPA item-count promotion does not establish a kg quantity threshold")
    if Decimal(amount) > Decimal(regular):
        raise ValueError("GPA promotional price exceeds regular price")
    if amount != regular or quantity is not None:
        yield make_offer(product, details, amount, regular, basis, quantity)


def make_offer(product, details, amount, reference, basis, quantity=None):
    return Offer(
        amount=amount,
        currency="BRL",
        basis=basis,
        reference_amount=reference,
        conditions=source_conditions(product, details, basis, quantity),
    )


def source_conditions(product, details, basis, quantity):
    return Conditions(
        payment_method="unknown",
        installments=None,
        membership_required=None,
        membership_program=None,
        coupon_required=None,
        minimum_quantity=quantity,
        description=condition_description(product, details, basis, quantity),
    )


def condition_description(product, details, basis, quantity):
    description = "Catálogo customerPlus=true; pagamento/clube/cupom não verificados."
    if basis == "kg":
        description += " Preço por kg; total depende da pesagem final."
    if quantity is not None:
        description += f" Preço médio anunciado para grupos de {quantity} unidades."
    restrictions = {
        "priceType": product.get("priceType"),
        "promotions": price_promotions(product, details),
    }
    return description + " Fonte: " + json.dumps(restrictions, ensure_ascii=False, default=str)
