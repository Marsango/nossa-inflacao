"""Preserve advertised kg prices and promotion conditions, without dividing portions."""

import json
from decimal import Decimal

from ..models import Conditions, Offer
from .values import source_money


def sale_basis(product) -> str:
    if (
        product.get("unidade_sigla") == "UN"
        and type(product.get("possui_unidade_diferente")) is bool
    ):
        return "package"
    if product.get("unidade_sigla") == "KG" and product.get("exibe_preco_original") is True:
        return "kg"
    if product.get("unidade_sigla") == "KG" and product.get("possui_unidade_diferente") is False:
        return "package"
    raise ValueError("Unsupported Hirota sale unit/portion format")


def product_offers(product, basis, warnings):
    if product.get("disponivel") is not True:
        return []
    promotion = product.get("oferta")
    if product.get("em_oferta") is True:
        return promoted_offers(product, promotion, basis, warnings)
    if product.get("em_oferta") is not False or promotion is not None:
        raise ValueError("Ambiguous Hirota promotion state")
    key = "preco_original" if basis == "kg" else "preco"
    return make_offer(product.get(key), None, basis, None, product)


def promoted_offers(product, promotion, basis, warnings):
    if isinstance(promotion, dict) and promotion.get("tipo_oferta_id") == 7:
        return tiered_offers(product, promotion, basis)
    if isinstance(promotion, dict) and promotion.get("tipo_oferta_id") == 5:
        return quantity_offers(product, promotion, basis, warnings)
    return promotional_offer(product, promotion, basis)


def tiered_offers(product, promotion, basis):
    validate_tiers(promotion, basis)
    bands = promotion["faixas_precos"]
    quantities = [validate_band(band) for band in bands]
    if len(set(quantities)) != len(quantities):
        raise ValueError("Duplicate Hirota quantity tiers")
    offers = make_offer(
        promotion.get("preco_oferta"), promotion.get("preco_antigo"), basis, promotion, product
    )
    offers.extend(tier_offer(product, promotion, basis, band) for band in bands)
    return offers


def validate_tiers(promotion, basis):
    if (
        basis != "package"
        or promotion.get("categoria") != "G"
        or promotion.get("familia") is not False
    ):
        raise ValueError("Unsupported Hirota mixed/weight quantity tiers")
    quantities = [
        promotion.get(key) for key in ("quantidade_minima", "quantidade_pagar", "quantidade_oferta")
    ]
    if any(type(quantity) is not int or quantity != 1 for quantity in quantities):
        raise ValueError("Unsupported Hirota quantity tier structure")
    bands = promotion.get("faixas_precos")
    if not isinstance(bands, list) or not bands:
        raise ValueError("Missing Hirota quantity tiers")


def validate_band(band):
    if not isinstance(band, dict):
        raise ValueError("Malformed Hirota quantity tier")
    quantity = band.get("quantidade")
    if type(quantity) is not int or quantity <= 1 or band.get("preco_oferta_fracao") is not None:
        raise ValueError("Unsupported Hirota quantity tier")
    if source_money(band.get("valor")) is None:
        raise ValueError("Missing Hirota tier price")
    return quantity


def tier_offer(product, promotion, basis, band):
    offers = make_offer(band["valor"], promotion.get("preco_antigo"), basis, promotion, product)
    offer = offers[0]
    conditions = offer.conditions
    conditions = conditions.model_copy(update={"minimum_quantity": str(band["quantidade"])})
    return offer.model_copy(update={"conditions": conditions})


def quantity_offers(product, promotion, basis, warnings):
    if basis != "package" or promotion.get("categoria") != "G":
        raise ValueError("Unsupported Hirota quantity promotion basis/category")
    if promotion.get("familia") or promotion.get("faixas_precos"):
        raise ValueError("Unsupported Hirota mixed/tiered quantity promotion")
    buy, pay = promotion.get("quantidade_minima"), promotion.get("quantidade_pagar")
    if type(buy) is not int or type(pay) is not int or not 0 < pay < buy:
        raise ValueError("Invalid Hirota quantity promotion")
    warnings.append(
        "quantity-promotion: regular displayed price retained; average price not inferred"
    )
    return make_offer(promotion.get("preco_antigo"), None, basis, None, product)


def promotional_offer(product, promotion, basis):
    if not isinstance(promotion, dict):
        raise ValueError("Missing Hirota promotion details")
    if (
        promotion.get("tipo_oferta_id") != 1
        or promotion.get("categoria") != "G"
        or promotion.get("faixas_precos")
        or promotion.get("familia")
    ):
        raise ValueError("Unsupported Hirota promotion; conditions require verification")
    if promotion.get("quantidade_pagar") != 1 or promotion.get("quantidade_oferta") != 1:
        raise ValueError("Unsupported Hirota quantity promotion")
    amount, reference = promotional_amounts(product, promotion, basis)
    return make_offer(amount, reference, basis, promotion, product)


def promotional_amounts(product, promotion, basis):
    if basis != "kg":
        return promotion.get("preco_oferta"), promotion.get("preco_antigo")
    if promotion.get("exibe_preco_original") is not True:
        raise ValueError("Promotion has no advertised kg price")
    return promotion.get("preco_original"), product.get("preco_original")


def make_offer(value, reference, basis, promotion, product):
    amount = source_money(value)
    if amount is None:
        return []
    return [
        Offer(
            amount=amount,
            currency="BRL",
            basis=basis,
            reference_amount=source_money(reference),
            conditions=offer_conditions(basis, promotion, product),
        )
    ]


def condition_description(basis, promotion, product):
    description = "Condições de pagamento, clube e cupom não informadas."
    if basis == "kg":
        description += " Preço anunciado por kg; porção aproximada, total sujeito ao peso final."
    details = promotion or product.get("oferta")
    if details is not None:
        description += " Oferta: " + json.dumps(details, ensure_ascii=False, default=str)
    if portion_priced(product, basis):
        description += " Preço por porção; embalagem fixa não verificada, sem conversão por kg."
    limits = {key: product.get(key) for key in ("quantidade_minima", "quantidade_maxima", "tags")}
    return (
        description + " Limites do anúncio: " + json.dumps(limits, ensure_ascii=False, default=str)
    )


def portion_priced(product, basis):
    return basis == "package" and product.get("possui_unidade_diferente") is True


def offer_conditions(basis, promotion, product):
    return Conditions(
        payment_method="unknown",
        installments=None,
        membership_required=None,
        membership_program=None,
        coupon_required=None,
        minimum_quantity=minimum_quantity(product, promotion),
        description=condition_description(basis, promotion, product),
    )


def minimum_quantity(product, promotion):
    values = [product.get("quantidade_minima")]
    if promotion is not None:
        values.append(promotion.get("quantidade_minima"))
    if None in values:
        return None
    quantities = [Decimal(str(value)) for value in values]
    if any(not quantity.is_finite() or quantity < 1 for quantity in quantities):
        raise ValueError("Invalid promotion minimum quantity")
    quantity = max(quantities)
    if quantity == 1:
        return None
    return format(quantity, "f")
