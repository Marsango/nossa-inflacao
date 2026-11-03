"""Explicit delivery and branch identity, resolved independently every run."""

from typing import Literal

from pydantic import Field, PrivateAttr

from ..config import Settings

API_BASE = "https://api.vendas.gpa.digital/pa/"


class PaoDeAcucarSettings(Settings):
    adapter: Literal["pao-de-acucar"] = "pao-de-acucar"
    shop_id: Literal["pao-de-acucar"] = "pao-de-acucar"
    shop_url: Literal["https://www.paodeacucar.com"] = "https://www.paodeacucar.com"
    store_id: str = Field(default="461", pattern=r"^[1-9][0-9]*$")
    postal_code: str = Field(default="04115090", pattern=r"^[0-9]{8}$")
    city: str = Field(default="São Paulo", min_length=1)
    state: str = Field(default="SP", pattern=r"^[A-Z]{2}$")
    delivery_type_id: int = Field(default=842, gt=0)
    branch_name: str = Field(default="1717 - Ricardo Jafet", pattern=r"^[0-9]+ - .+$")
    branch_postal_code: str = Field(default="04115090", pattern=r"^[0-9]{8}$")
    branch_address_number: int = Field(default=299, ge=0)
    max_catalog_pages: int = Field(default=2000, ge=1, le=3000)
    _context_verified: bool = PrivateAttr(default=False)

    def verify_context(self) -> None:
        self._context_verified = True

    def require_context(self) -> None:
        if not self._context_verified:
            raise ValueError("Pão de Açúcar delivery context must be resolved before collection")
