"""Use shared monitoring, batching, reporting and isolated delivery spools."""

from datetime import UTC, datetime

from ..adapters import Adapter
from .catalog import search_pages as search_pages
from .catalog import validate_page
from .config import AtacadaoSettings
from .parsing import parse_products
from .source import fetch_products, prepare_context
from .stock import with_availability


def discover(requester, settings, query, limit):
    document, source_url = fetch_products(requester, settings, query, 0, min(limit, 50))
    observed_at = datetime.now(UTC)
    products, _ = validate_page(document, 0, min(limit, 50), None, set())
    products = with_availability(requester, settings, products)
    return parse_products(products, settings, source_url, observed_at)


ADAPTER = Adapter("atacadao", AtacadaoSettings, search_pages, discover, prepare=prepare_context)
