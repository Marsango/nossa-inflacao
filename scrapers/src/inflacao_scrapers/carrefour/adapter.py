"""Carrefour uses the existing collection, batching, diagnostics and delivery runner."""

from ..adapters import Adapter
from .catalog import catalog_pages, validate_page
from .config import CarrefourSettings
from .parsing import parse_products
from .session import open_session
from .source import fetch_products


def prepare_context(requester, settings: CarrefourSettings) -> CarrefourSettings:
    print(
        f"shop=carrefour schedule_id={settings.schedule_id} city={settings.city} "
        f"state={settings.state} postal_code={settings.postal_code} preparing",
        flush=True,
    )
    return settings


def discover(requester, settings, query, limit):
    with open_session(settings) as driver:
        document, url, observed_at = fetch_products(driver, settings, query, 1)
        products, _ = validate_page(document, 1, None, set())
        result = parse_products(products, settings, url, observed_at)
    result.observations = result.observations[:limit]
    return result


ADAPTER = Adapter(
    "carrefour",
    CarrefourSettings,
    None,
    discover,
    prepare=prepare_context,
    catalog_pages=catalog_pages,
)
