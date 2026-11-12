"""Reuse exact VTEX parsing, bounded searches, regional resolution and delivery."""

from ..adapters import Adapter
from ..vtex.fetching import discover
from ..vtex.regional import prepare_region
from ..vtex.search import search_pages
from .config import GBarbosaSettings

ADAPTER = Adapter("gbarbosa", GBarbosaSettings, search_pages, discover, prepare=prepare_region)
