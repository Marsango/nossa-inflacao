"""Use visible BRL amounts; never trust template metadata or analytics floats."""

import re
from decimal import Decimal

from ..models import Conditions, Offer
from ..scope import normalize
from .html import class_nodes, suffix_nodes, text, unique_text

CONTEXT_NOTE = (
    "Catálogo público online Sonda. Loja, CEP e condições de retirada não selecionados; "
    "uniformidade regional de preços não verificada. Estoque sujeito à data da entrega. "
    "Condições de pagamento, clube e cupom não informadas."
)


def money(value):
    if value is None:
        return None
    if not re.fullmatch(r"(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}", value):
        raise ValueError("Invalid Sonda visible BRL price")
    amount = Decimal(value.replace(".", "").replace(",", "."))
    if amount == 0:
        return None
    return format(amount, ".2f")


def price_basis(card, name):
    if re.search(r"(?:/\s*kg|por\s+(?:kg|quilo)|peso\s+vari[aá]vel)", name, re.I):
        return None
    if portion_priced(card, name) and not declared_portion(name):
        return None
    return "package"


def declared_portion(name):
    return re.search(r"\b\d+(?:[.,]\d+)?\s*(?:kg|g|ml|l|un(?:idades?)?)\b", name, re.I) is not None


def offers(card, basis):
    value = unique_text(suffix_nodes(card, "_lblValorPor"), "selling price", False)
    amount = money(value)
    if amount is None:
        return []
    promotion = promotion_terms(card, amount)
    reference = money(unique_text(suffix_nodes(card, "_lblValorDe"), "reference price", False))
    regular = make_offer(card, amount, reference, basis)
    if promotion is None:
        return [regular]
    quantity, advertised_average = promotion
    return [regular, make_offer(card, advertised_average, amount, basis, quantity)]


def make_offer(card, amount, reference, basis, quantity=None):
    return Offer(
        amount=amount,
        currency="BRL",
        basis=basis,
        reference_amount=reference,
        conditions=conditions(card, quantity),
    )


def conditions(card, quantity=None):
    discounts = class_nodes(card, "product--discount")
    labels = [unique_text([node], "discount") for node in discounts]
    if any(not re.fullmatch(r"\d+% OFF", label) for label in labels):
        raise ValueError("Unsupported Sonda discount conditions")
    return Conditions(
        payment_method="unknown",
        installments=None,
        membership_required=None,
        membership_program=None,
        coupon_required=None,
        minimum_quantity=quantity,
        description=condition_description(card, labels, quantity),
    )


def portion_priced(card, name):
    category = normalize(unique_text(class_nodes(card, "js-titulo"), "category"))
    if any(word in category for word in ("acougue", "hortifruti", "peixaria", "padaria")):
        return True
    if "frios e laticinios" not in category:
        return False
    fixed = ("leite ", "iogurte ", "manteiga ", "margarina ", "requeijao ", "bebida lactea ")
    return not normalize(name).startswith(fixed)


def condition_description(card, labels, quantity):
    name = unique_text(class_nodes(card, "product--title"), "product name")
    description = CONTEXT_NOTE + " " + " ".join(labels)
    if portion_priced(card, name):
        description += (
            " Preço anunciado pelo item/porção; peso fixo não verificado, sem conversão por kg."
        )
    description += " " + badge_text(card)
    if quantity is not None:
        description += f" Preço médio anunciado para grupos de {quantity} unidades."
    return description.strip()


def badge_text(card):
    return " ".join(text(node) for node in class_nodes(card, "product--badges")).strip()


def promotion_terms(card, amount):
    description = badge_text(card)
    if not description:
        return None
    match = re.fullmatch(
        r"([1-9]\d*) ([1-9]\d*) Nesta promoção a unid\. sai por: ([\d.,]+)", description
    )
    if match is None:
        return second_unit_terms(description, amount)
    return quantity_terms(match, amount)


def quantity_terms(match, amount):
    advertised = money(match[3])
    if not 0 < int(match[2]) < int(match[1]) or advertised is None:
        raise ValueError("Invalid Sonda quantity promotion")
    if Decimal(advertised) >= Decimal(amount):
        raise ValueError("Sonda quantity promotion is not lower than the regular price")
    expected = Decimal(amount) * Decimal(match[2]) / Decimal(match[1])
    verify_promotion_amount(advertised, expected)
    return match[1], advertised


def second_unit_terms(description, amount):
    match = re.fullmatch(
        r"([1-9]\d?)% na 2ª UNIDADE Nesta promoção a 2ª UNIDADE sai por: ([\d.,]+)", description
    )
    if match is None or money(match[2]) is None:
        raise ValueError(f"Unsupported Sonda promotion/badge: {description}")
    expected = Decimal(amount) * (100 - Decimal(match[1])) / 100
    verify_promotion_amount(money(match[2]), expected)
    return None


def verify_promotion_amount(advertised, expected):
    if abs(Decimal(advertised) - expected) > Decimal("0.01"):
        raise ValueError(
            "Sonda advertised promotion price disagrees with its quantity/discount label"
        )
