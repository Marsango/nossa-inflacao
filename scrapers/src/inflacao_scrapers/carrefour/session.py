"""One ephemeral Botasaurus driver per CEP; no result cache, exports or implicit retries."""

import time
from contextlib import contextmanager

from ..scope import normalize
from .decoding import ReferenceTable

REGIONAL_RECORDER = """
window.carrefourRegionResponse = null;
const originalFetch = window.fetch;
window.fetch = async function(input, options) {
  const response = await originalFetch(input, options);
  if (String(input).split('?')[0].endsWith('/action/set-regionalization.data')) {
    const text = await response.clone().text();
    window.carrefourRegionResponse = {status: response.status, text};
  }
  return response;
};
"""
CONTEXT_SCRIPT = """return {
  postalCode: localStorage.getItem('vtex:postalCode'),
  regionId: localStorage.getItem('vtex:regionId'),
  deliveryType: localStorage.getItem('vtex:deliveryType'),
  text: document.body.innerText.slice(0, 3000)
};"""


@contextmanager
def open_session(settings):
    driver = create_driver(settings)
    try:
        initialize_context(driver, settings)
        yield driver
    finally:
        driver.close()


def create_driver(settings):
    try:
        from botasaurus_driver import Driver
    except ImportError as error:
        raise ValueError(
            "Carrefour requires the browser extra and Chrome; see scrapers/README.md"
        ) from error
    return Driver(
        headless=True,
        block_images=True,
        window_size=(1440, 1000),
        chrome_executable_path=settings.chrome_executable_path,
    )


def initialize_context(driver, settings):
    driver.get(settings.shop_url, timeout=settings.timeout_seconds)
    driver.run_js(REGIONAL_RECORDER)
    driver.click('button[aria-label="abre o modal de regionalização"]')
    driver.type("#cep", settings.postal_code)
    driver.run_js("document.querySelector('#cep').closest('form').requestSubmit()")
    response = await_region(driver, settings.timeout_seconds)
    if response["status"] != 200:
        raise ValueError(f"Carrefour regional selection HTTP {response['status']}")
    result = regional_selection(response["text"])
    validate_selection(result, settings)
    await_context(driver, settings)


def regional_selection(raw: str) -> dict:
    document = ReferenceTable(raw).resolve()
    data = document.get("data")
    if not isinstance(data, dict):
        raise ValueError("Carrefour regional response malformed")
    result = data.get("result")
    if not isinstance(result, dict):
        raise ValueError("Carrefour did not resolve a store for the selected delivery CEP")
    return result


def await_region(driver, timeout):
    deadline, response = time.monotonic() + timeout, None
    while response is None and time.monotonic() < deadline:
        response = driver.run_js("return window.carrefourRegionResponse")
        time.sleep(0.2)
    if response is None:
        raise ValueError("Carrefour regional selection missing or blocked; collection not started")
    return response


def validate_selection(result, settings):
    context = result.get("regionContextProps", {})
    if result.get("regionId") != settings.region_id:
        raise ValueError("Carrefour selected another region; collection not started")
    if str(result.get("postalCode", "")).replace("-", "") != settings.postal_code:
        raise ValueError("Carrefour selected another CEP; collection not started")
    if context.get("regionId") != settings.region_id or context.get("status") != "loaded":
        raise ValueError("Carrefour regional context not loaded")
    if context.get("deliveryType") != "residential":
        raise ValueError("Carrefour did not select delivery")
    if normalize(settings.city) not in normalize(context.get("deliveryAddress", "")):
        raise ValueError("Carrefour returned another city")


def await_context(driver, settings):
    deadline = time.monotonic() + settings.timeout_seconds
    while time.monotonic() < deadline and not matching_context(
        driver.run_js(CONTEXT_SCRIPT), settings
    ):
        time.sleep(0.2)
    require_context(driver, settings)


def matching_context(context, settings):
    return (
        context.get("regionId") == settings.region_id
        and str(context.get("postalCode", "")).replace("-", "") == settings.postal_code
        and context.get("deliveryType") == "residential"
        and normalize(settings.city) in normalize(context.get("text", ""))
    )


def require_context(driver, settings):
    context = driver.run_js(CONTEXT_SCRIPT)
    if not matching_context(context, settings):
        raise ValueError("Carrefour delivery session changed; collection incomplete")
