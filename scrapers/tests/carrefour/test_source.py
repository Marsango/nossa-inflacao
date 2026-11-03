from unittest.mock import Mock

import pytest

from inflacao_scrapers.carrefour import session, source
from inflacao_scrapers.carrefour.config import CarrefourSettings

from .conftest import selected_region, selected_storefront


def test_region_response_requires_expected_cep_city_delivery_and_region(settings):
    session.validate_selection(selected_region(settings), settings)
    for key in ["regionId", "postalCode"]:
        changed = selected_region(settings)
        changed[key] = "wrong"
        with pytest.raises(ValueError):
            session.validate_selection(changed, settings)
    changed = selected_region(settings)
    changed["regionContextProps"]["deliveryType"] = "pickup"
    with pytest.raises(ValueError, match="delivery"):
        session.validate_selection(changed, settings)


def test_lost_session_context_stops_fetching(settings, monkeypatch):
    driver = Mock()
    driver.run_js.return_value = {**selected_storefront(settings), "regionId": "another"}
    request = Mock()
    monkeypatch.setattr(source, "browser_request", request)
    with pytest.raises(ValueError, match="session changed"):
        source.fetch_products(driver, settings, "arroz", 1)
    request.assert_not_called()


def test_browser_is_closed_on_preparation_failure_and_consumer_failure(settings, monkeypatch):
    driver = Mock()
    monkeypatch.setattr(session, "create_driver", lambda settings: driver)
    initialize = Mock(side_effect=ValueError("blocked"))
    monkeypatch.setattr(session, "initialize_context", initialize)
    with pytest.raises(ValueError, match="blocked"), session.open_session(settings):
        pass
    driver.close.assert_called_once()
    driver.close.reset_mock()
    initialize.side_effect = None
    with pytest.raises(RuntimeError), session.open_session(settings):
        raise RuntimeError("delivery failed")
    driver.close.assert_called_once()


@pytest.mark.parametrize(
    "change",
    [
        {"status": 403},
        {"age": "1"},
        {"type": "text/html"},
        {"url": "https://other.example"},
    ],
)
def test_challenges_cached_data_and_redirects_cannot_be_parsed(change):
    url = "https://mercado.carrefour.com.br/busca/arroz.data"
    response = {"status": 200, "url": url, "type": "text/x-script", "age": None, "text": "[]"}
    with pytest.raises(ValueError):
        source.validate_response({**response, **change}, url)


def test_search_paths_encode_query_text_and_always_use_fresh_request_identity(settings):
    first = source.search_url(settings, "açúcar / cristal", 2)
    second = source.search_url(settings, "açúcar / cristal", 2)
    assert first != second
    assert "a%C3%A7%C3%BAcar%20%2F%20cristal.data?page=2" in first
    assert "_ir=" in first


def test_unverified_settings_are_rejected():
    with pytest.raises(ValueError, match="Unverified"):
        CarrefourSettings(scraper_id="collector", postal_code="99999999")
