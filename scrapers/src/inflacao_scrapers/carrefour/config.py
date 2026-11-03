"""Independently verified Carrefour delivery contexts, with explicit geography."""

from typing import Literal, Self

from pydantic import Field, model_validator

from ..config import Settings

CONTEXTS = {
    "SP": ("São Paulo", "01310100", "v2.4FC957AB8941A10397B85207B23C2F55"),
    "RJ": ("Rio de Janeiro", "22041001", "v2.7270B316E593B206E6E0275E7718FBF4"),
    "AM": ("Manaus", "69005040", "v2.BF533D0AEECE42C36BD9B8DA285BEF38"),
    "DF": ("Brasília", "70390025", "v2.3AAC323080B05FB702A3AB2ABAA90E3B"),
    "ES": ("Vitória", "29010001", "v2.7D0ED687024A66050E0FD3832B8BD6AA"),
    "GO": ("Goiânia", "74810100", "v2.F05A3DA1C76D4CCCAFB4EBFB21F46381"),
    "MG": ("Belo Horizonte", "30130010", "v2.0E68B2A9BF71F2194EF2890250AAAAF4"),
    "MS": ("Campo Grande", "79032040", "v2.11FA59941738A4965184405D490939EC"),
    "PB": ("João Pessoa", "58039000", "v2.80E9F1AA89E1A658455D7B622AA088BF"),
    "PE": ("Recife", "51021000", "v2.B8D4DEE82CCFA7FBA645F5E26E2A24C2"),
    "PR": ("Curitiba", "80730201", "v2.DBEC9A35D9DE71C4BB85CA48A5354448"),
    "RN": ("Natal", "59020100", "v2.D9CE56FB0EB73802601410FB432111F4"),
    # RS geography is verified, but inconsistent source pagination prevents scheduling.
    "RS": ("Porto Alegre", "91530010", "v2.053EECC52F7DDB6D888BC8C75F60ADB2"),
    "SC": ("Florianópolis", "88015200", "v2.053EF8325AA06E6F886118F67CAFA4AB"),
}


class CarrefourSettings(Settings):
    adapter: Literal["carrefour"] = "carrefour"
    shop_id: Literal["carrefour"] = "carrefour"
    shop_url: Literal["https://mercado.carrefour.com.br"] = "https://mercado.carrefour.com.br"
    city: str = "São Paulo"
    state: str = Field(default="SP", pattern=r"^[A-Z]{2}$")
    postal_code: str = "01310100"
    region_id: str = CONTEXTS["SP"][2]
    seller_id: Literal["1"] = "1"
    store_id: str = "region:" + CONTEXTS["SP"][2] + "/seller:1"
    chrome_executable_path: str | None = None
    max_search_pages: int = Field(default=100, ge=1, le=200)
    max_catalog_pages: int = Field(default=1000, ge=1, le=3000)

    @model_validator(mode="after")
    def verified_configuration(self) -> Self:
        expected = CONTEXTS.get(self.state)
        if expected is None:
            raise ValueError("Unverified Carrefour capital")
        if (self.city, self.postal_code, self.region_id) != expected:
            raise ValueError("Unverified Carrefour city, CEP or region")
        if self.store_id != f"region:{self.region_id}/seller:{self.seller_id}":
            raise ValueError("Carrefour store_id must preserve the selected delivery region")
        return self
