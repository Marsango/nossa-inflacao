"""Map independent advertised promotions without assuming discounts stack."""

from .prices import source_money

RESTRICTIONS = ("paymentFormName", "subscriptionPrice", "appExclusive", "isHeterogeneousPromotion")


def promotion_list(details):
    promotions = details.get("productPromotions", [])
    if not isinstance(promotions, list) or any(not isinstance(item, dict) for item in promotions):
        raise ValueError("Malformed GPA promotion list")
    if details.get("productPromotion") not in (None, *promotions):
        raise ValueError("GPA selected promotion missing from promotion list")
    return promotions


def price_promotions(product, details):
    promotions = promotion_list(details)
    if details is product:
        return promotions
    parents = promotion_list(product)
    return [weight_promotion(promotion, parents) for promotion in promotions]


def weight_promotion(promotion, parents):
    matches = [parent for parent in parents if parent.get("ruleId") == promotion.get("ruleId")]
    if len(matches) != 1:
        raise ValueError("GPA kg promotion has no unique parent conditions")
    parent = matches[0]
    overlapping = set(promotion).intersection(parent).difference({"unitPrice"})
    if any(promotion[key] != parent[key] for key in overlapping):
        raise ValueError("GPA kg and parent promotion conditions disagree")
    return {**parent, **promotion}


def minimum_quantity(promotion):
    if any(promotion.get(key) for key in RESTRICTIONS):
        raise ValueError("Unsupported GPA quantity/payment/application promotion")
    buy, pay = promotion.get("promotionQuantityBuy"), promotion.get("promotionQuantityPayFor")
    if buy is not None or pay is not None:
        return quantity_promotion(buy, pay)
    unity = promotion.get("promotionPercentOffOnUnity")
    if unity is None or type(unity) is int and unity == 1:
        return None
    if type(unity) is int and unity > 1:
        return str(unity)
    raise ValueError("Invalid GPA unit-discount promotion")


def quantity_promotion(buy, pay):
    if type(buy) is not int or type(pay) is not int or not 0 < pay < buy:
        raise ValueError("Unsupported GPA quantity/payment/application promotion")
    return str(buy)


def promotional_price(promotion):
    quantity = minimum_quantity(promotion)
    amount = source_money(promotion.get("unitPrice"))
    if amount is None:
        raise ValueError("GPA promotion has no advertised unit price")
    return amount, quantity
