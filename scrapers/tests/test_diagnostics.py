import json
from types import SimpleNamespace

import httpx
import pytest

from inflacao_scrapers.collection import CollectionRun
from inflacao_scrapers.diagnostics.delivery import complete, diagnostic_spool, try_replay
from inflacao_scrapers.diagnostics.report import encode_report
from inflacao_scrapers.transport import Requester


def configuration():
    return SimpleNamespace(
        scraper_id="collector",
        shop_id="mambo",
        adapter="mambo",
        core_url="https://core.example",
        spool_path="prices.sqlite3",
        spool_capacity_bytes=1024 * 1024,
    )


def test_named_report_bounds_and_counts():
    run = CollectionRun("mambo")
    for _ in range(110):
        run.warning("x" * 3000)
    report = json.loads(encode_report(run, configuration()))
    assert report["scraper_name"] == "Mambo"
    assert report["warnings"] == 110
    assert report["omitted"] == 109
    assert len(report["diagnostics"]) == 1
    assert len(report["diagnostics"][0]["message"]) == 2000


def test_errors_replace_warnings_when_report_is_full():
    run = CollectionRun("mambo")
    for index in range(110):
        run.warning(f"page={index}: provenance")
    run.issue("category=food: pagination failed")
    run.issue("category=food: pagination failed")
    report = json.loads(encode_report(run, configuration()))
    assert report["errors"] == 2 and report["warnings"] == 110
    assert report["omitted"] == 12
    assert len(report["diagnostics"]) == 100
    assert report["diagnostics"][-1]["severity"] == "error"


def test_report_byte_limit_discards_warnings_before_errors():
    run = CollectionRun("mambo")
    run.issue("early collection failure")
    for index in range(99):
        run.warning(f"{index}:" + "界" * 1990)
    payload = encode_report(run, configuration())
    report = json.loads(payload)
    assert len(payload) <= 256 * 1024
    assert report["diagnostics"][0]["message"] == "early collection failure"
    assert len(report["diagnostics"]) + report["omitted"] == 100


def test_durable_replay_preserves_payload(tmp_path):
    settings = configuration()
    arguments = SimpleNamespace(config=tmp_path / "config.toml")
    run = CollectionRun("mambo")
    run.issue("target=coffee: no matching listings")
    with diagnostic_spool(settings, arguments) as spool:
        fail_delivery(spool, settings, run)
        pending = list(spool.pending())
        assert len(pending) == 1
    with diagnostic_spool(settings, arguments) as spool:
        acknowledge_delivery(spool, settings, pending[0][1])
        assert list(spool.pending()) == []
    assert not (tmp_path / "prices.sqlite3").exists()


def fail_delivery(spool, settings, run):
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    with httpx.Client(transport=transport) as client:
        assert not complete(spool, Requester(client, attempts=1), settings, "secret", run)


def acknowledge_delivery(spool, settings, payload):
    def handler(request):
        assert request.content == payload
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert try_replay(spool, Requester(client, attempts=1), settings, "secret")


def test_queue_exhaustion_preserves_existing_reports(tmp_path):
    settings = configuration()
    with diagnostic_spool(settings, SimpleNamespace(config=tmp_path / "config.toml")) as spool:
        spool.capacity = 4
        spool.enqueue_payload("first", b"1234")
        with pytest.raises((RuntimeError, ValueError)):
            spool.enqueue_payload("second", b"1")
        assert list(spool.pending()) == [("first", b"1234")]


def test_schema_and_secret_redaction():
    from pathlib import Path

    from jsonschema import Draft202012Validator, FormatChecker

    run = CollectionRun("mambo")
    run.issue("Failed request with sensitive-token")
    report = json.loads(encode_report(run, configuration(), "sensitive-token"))
    assert "sensitive-token" not in json.dumps(report)
    schema_path = Path(__file__).parents[2] / "docs/contracts/scraper-reports/v1/schema.json"
    schema = json.loads(schema_path.read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.validate(report)
    validator.validate(json.loads(schema_path.with_name("example.json").read_text()))
