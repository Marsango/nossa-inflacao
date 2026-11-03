"""Fetch fresh source text inside the verified browser session, never JSON.parse prices."""

import time
from datetime import UTC, datetime
from urllib.parse import quote, urlencode
from uuid import uuid4

from .config import CarrefourSettings
from .decoding import ReferenceTable
from .session import require_context

FETCH_SCRIPT = """
return (async () => {
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), args.timeout);
try {
  const response = await fetch(args.url, {cache:'no-store', credentials:'same-origin',
    redirect:'error', signal:controller.signal,
    headers:{'Cache-Control':'no-cache, max-age=0','Pragma':'no-cache'}});
  const text = await response.text();
  return {status:response.status, url:response.url, text,
    type:response.headers.get('content-type'), age:response.headers.get('age')};
} finally { clearTimeout(timeout); }
})();
"""


def fetch_products(
    driver,
    settings: CarrefourSettings,
    query: str,
    page: int,
) -> tuple[dict, str, datetime]:
    require_context(driver, settings)
    time.sleep(settings.request_interval_seconds)
    url = search_url(settings, query, page)
    response = browser_request(driver, settings, url)
    observed_at = datetime.now(UTC)
    validate_response(response, url)
    require_context(driver, settings)
    document = ReferenceTable(response["text"]).route("routes/busca.$term")
    if document.get("term") != query:
        raise ValueError("Carrefour search term changed; collection incomplete")
    return document, url, observed_at


def browser_request(driver, settings, url):
    arguments = {"url": url, "timeout": int(settings.timeout_seconds * 1000)}
    try:
        return driver.run_js(FETCH_SCRIPT, arguments, timeout=settings.timeout_seconds + 5)
    except Exception as error:
        raise ValueError("Carrefour browser request failed; collection incomplete") from error


def validate_response(response, url):
    if response.get("status") != 200 or response.get("url") != url:
        raise ValueError(f"Carrefour source HTTP {response.get('status')}; collection incomplete")
    if int(response.get("age") or "0") > 0:
        raise ValueError("Carrefour returned aged source data; collection incomplete")
    if not str(response.get("type", "")).startswith("text/x-script"):
        raise ValueError("Carrefour source type changed; possible challenge")
    if not isinstance(response.get("text"), str) or len(response["text"]) > 8 * 1024 * 1024:
        raise ValueError("Carrefour source absent or oversized")


def search_url(settings, query, page):
    parameters = urlencode({"page": page, "_ir": str(uuid4())})
    return settings.shop_url + "/busca/" + quote(query, safe="") + ".data?" + parameters
