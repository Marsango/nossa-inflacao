"""Verified delivery CEPs; never label the national electronics seller as groceries."""

from typing import Literal, Self

from pydantic import model_validator

from ..vtex.config import VtexSettings

CONTEXTS = {
    ("49026010", "gbarbosab006", "Aracaju", "SE"),
    ("41820020", "gbarbosab035", "Salvador", "BA"),
    ("57035000", "gbarbosab084", "Maceió", "AL"),
}


class GBarbosaSettings(VtexSettings):
    adapter: Literal["gbarbosa"] = "gbarbosa"
    shop_id: Literal["gbarbosa"] = "gbarbosa"
    shop_url: Literal["https://www.gbarbosa.com.br"] = "https://www.gbarbosa.com.br"
    sales_channel: Literal["1"] = "1"
    seller_id: Literal["1"] = "1"
    postal_code: str = "49026010"
    regional_seller_id: str = "gbarbosab006"
    store_id: str = "seller:gbarbosab006"
    city: str = "Aracaju"
    state: str = "SE"

    @model_validator(mode="after")
    def verified_delivery(self) -> Self:
        context = self.postal_code, self.regional_seller_id, self.city, self.state
        if context not in CONTEXTS:
            raise ValueError("Unverified GBarbosa delivery context")
        return self

    def supports_kilogram_prices(self) -> bool:
        context = self.postal_code, self.regional_seller_id, self.city, self.state
        return self.region_id is not None and context in CONTEXTS
