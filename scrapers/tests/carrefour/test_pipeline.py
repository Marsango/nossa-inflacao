import json
import sys
from types import SimpleNamespace

import httpx
from stores.test_pipeline import install_mock_runtime, monitoring_response

from inflacao_scrapers import cli
from inflacao_scrapers.carrefour import catalog, session
from inflacao_scrapers.delivery import Spool

from .conftest import OBSERVED_AT, captured_search, configuration


def write_configuration(tmp_path):
    blocks = []
    for state in ["SP", "RJ"]:
        settings = configuration(state)
        values = settings.model_dump(exclude_none=True)
        values.update(schedule_id="carrefour-" + state.lower(), spool_path=state + ".sqlite3")
        blocks.append(
            "[[scrapers]]\n"
            + "\n".join(
                key + " = " + json.dumps(value, ensure_ascii=False) for key, value in values.items()
            )
        )
    path = tmp_path / "config.toml"
    path.write_text("\n\n".join(blocks))
    return path


def install_browser(monkeypatch, events, blocked):
    def create_driver(settings):
        events.append(("open", settings.state))
        return SimpleNamespace(close=lambda: events.append(("close", settings.state)))

    monkeypatch.setattr(session, "create_driver", create_driver)
    monkeypatch.setattr(
        session, "initialize_context", lambda driver, settings: require_unblocked(settings, blocked)
    )
    monkeypatch.setattr(catalog, "fetch_products", source_response)


def require_unblocked(settings, blocked):
    if settings.state == blocked:
        raise ValueError("Carrefour HTTP 403; collection incomplete")


def source_response(driver, settings, query, page):
    document = captured_search(settings.state)
    document["totalCount"] = 3
    document["pagination"].update(current={"index": 1}, count=1)
    return document, settings.shop_url + "/busca/arroz.data", OBSERVED_AT


def execute(tmp_path, monkeypatch, blocked=None, failed_delivery=False):
    submissions, events = [], []
    install_browser(monkeypatch, events, blocked)
    install_mock_runtime(
        monkeypatch, lambda request: core_response(request, submissions, failed_delivery)
    )
    monkeypatch.setenv("INGESTION_TOKEN", "secret")
    monkeypatch.setattr(
        sys, "argv", ["scraper", "--config", str(write_configuration(tmp_path)), "collect"]
    )
    return cli.main(), submissions, events


def core_response(request, submissions, failed_delivery):
    assert request.url.host == "127.0.0.1"
    if request.method == "GET":
        return monitoring_response()
    if request.url.path.endswith("scraper-reports"):
        return httpx.Response(201)
    if request.url.path.endswith("submissions"):
        submissions.append(request.content)
        return httpx.Response(401 if failed_delivery else 202)
    return httpx.Response(202)


def test_two_regions_submit_contract_observations_without_spools(tmp_path, monkeypatch):
    status, submissions, events = execute(tmp_path, monkeypatch)
    assert status == 0 and len(submissions) == 2
    contexts = [json.loads(body)["observations"][0]["context"] for body in submissions]
    assert {context["state"] for context in contexts} == {"SP", "RJ"}
    assert len({context["store_id"] for context in contexts}) == 2
    assert_closed_sessions(events)
    assert not list(tmp_path.glob("*.sqlite3"))


def test_blocked_first_city_still_allows_second_city_collection(tmp_path, monkeypatch):
    status, submissions, events = execute(tmp_path, monkeypatch, blocked="SP")
    assert status == 1 and len(submissions) == 1
    assert json.loads(submissions[0])["observations"][0]["context"]["state"] == "RJ"
    assert_closed_sessions(events)


def test_delivery_failure_closes_sessions_and_keeps_byte_exact_isolated_spools(
    tmp_path, monkeypatch
):
    status, submissions, events = execute(tmp_path, monkeypatch, failed_delivery=True)
    assert status == 1 and len(submissions) == 2
    assert_closed_sessions(events)
    for attempted in submissions:
        document = json.loads(attempted)
        state = document["observations"][0]["context"]["state"]
        with Spool(tmp_path / (state + ".sqlite3")) as spool:
            assert next(spool.pending())[1] == attempted
        assert document["scraper_id"] == "authorized-collector"


def assert_closed_sessions(events):
    assert len(events) == 4
    assert {state for action, state in events} == {"SP", "RJ"}
    for index in (0, 2):
        action, state = events[index]
        assert action == "open"
        assert events[index + 1] == ("close", state)
