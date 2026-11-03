"""One explicit branch per schedule; never infer geography from a URL alone."""

from typing import Literal

from pydantic import Field, PrivateAttr

from ..config import Settings


class AtacadaoSettings(Settings):
    adapter: Literal["atacadao"] = "atacadao"
    shop_id: Literal["atacadao"] = "atacadao"
    shop_url: Literal["https://www.atacadao.com.br"] = "https://www.atacadao.com.br"
    store_id: str = Field(default="60", pattern=r"^[1-9][0-9]*$")
    seller_id: str = Field(default="atacadaobr60", pattern=r"^atacadaobr[1-9][0-9]*$")
    branch_slug: str = Field(default="vila-maria", pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    branch_name: str = Field(default="Vila Maria", min_length=1)
    branch_postal_code: str = Field(default="02170901", pattern=r"^[0-9]{8}$")
    city: str = Field(default="São Paulo", min_length=1)
    state: str = Field(default="SP", pattern=r"^[A-Z]{2}$")
    sales_channel: Literal["1"] = "1"
    max_search_pages: int = Field(default=50, ge=1, le=100)
    _context_verified: bool = PrivateAttr(default=False)

    def verify_context(self) -> None:
        self._context_verified = True

    def require_context(self) -> None:
        if not self._context_verified:
            raise ValueError("Atacadão branch must be verified before collection")
