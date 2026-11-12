from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from inflacao_scrapers.carrefour import session
from inflacao_scrapers.execution.browser import browser_session
from inflacao_scrapers.hirota import browser


def test_browser_limit_is_shared_between_adapters(monkeypatch):
    driver = SimpleNamespace(close=lambda: assert_browser_locked())
    monkeypatch.setattr(session, "create_driver", lambda settings: checked_driver(driver))
    monkeypatch.setattr(session, "initialize_context", lambda *arguments: assert_browser_locked())
    monkeypatch.setattr(browser, "isolated_session", lambda settings: assert_browser_locked())
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(browser_task, range(8)))
    assert results == [None] * 8
    assert not browser_session.locked()


def browser_task(index):
    if index % 2:
        return browser.bootstrap_session(None)
    with session.open_session(None):
        assert_browser_locked()


def assert_browser_locked():
    assert browser_session.locked()


def checked_driver(driver):
    assert_browser_locked()
    return driver


def test_browser_initialization_failure_closes_driver_and_releases_limit(monkeypatch):
    closed = []
    driver = SimpleNamespace(close=lambda: closed.append(True))
    monkeypatch.setattr(session, "create_driver", lambda settings: driver)
    monkeypatch.setattr(session, "initialize_context", fail_session)
    with pytest.raises(ValueError, match="Context failed"):
        with session.open_session(None):
            pytest.fail("Broken context must not be used")
    assert closed == [True]
    assert not browser_session.locked()


def fail_session(*arguments):
    raise ValueError("Context failed")


def test_browser_collection_failure_releases_limit(monkeypatch):
    closed = []
    driver = SimpleNamespace(close=lambda: closed.append(True))
    monkeypatch.setattr(session, "create_driver", lambda settings: driver)
    monkeypatch.setattr(session, "initialize_context", lambda *arguments: None)
    with pytest.raises(RuntimeError, match="Collection failed"):
        with session.open_session(None):
            raise RuntimeError("Collection failed")
    assert closed == [True]
    assert not browser_session.locked()


def test_hirota_failure_releases_shared_browser_limit(monkeypatch):
    monkeypatch.setattr(browser, "isolated_session", fail_session)
    with pytest.raises(ValueError, match="Context failed"):
        browser.bootstrap_session(None)
    assert not browser_session.locked()
