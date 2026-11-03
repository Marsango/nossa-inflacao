"""Two contexts of one retailer retain separate submissions and failed-delivery spools."""
import json
import sys

import httpx
from stores.test_pipeline import install_mock_runtime, monitoring_response

from inflacao_scrapers import cli
from inflacao_scrapers.delivery import Spool

from .test_capitals import CAPITALS
from .test_source import FIXTURES


def source_response(request):
    if request.url.path.endswith("deliveryOptions"):
        postal_code = request.url.params["zipCode"]
        capital = next(item for item in CAPITALS if item["settings"]["postal_code"] == postal_code)
        return httpx.Response(200, json=capital["delivery"])
    if request.url.path.endswith("humanization"):
        identity = request.url.path.split("/")[-2]
        capital = next(item for item in CAPITALS if item["settings"]["store_id"] == identity)
        return httpx.Response(200, json=capital["branch"])
    if request.url.path.endswith("categories"):
        return httpx.Response(200, json={"content": [{"uiLink": "/alimentos"}]})
    raw = (FIXTURES / "pao-de-acucar-rice.json").read_bytes()
    raw = raw.replace(b'"totalProducts":58', b'"totalProducts":12')
    return httpx.Response(200, content=raw.replace(b'"totalPages":5', b'"totalPages":1'))


def response(request, submissions):
    if request.url.host != "127.0.0.1":
        assert "authorization" not in request.headers
        return source_response(request)
    if request.url.path.endswith("scraper-reports"):
        return httpx.Response(201)
    if request.method == "GET":
        return monitoring_response()
    submissions.append(request.content)
    return httpx.Response(401)


def write_configuration(tmp_path):
    entries = []
    for capital in CAPITALS[:2]:
        values = {"adapter": "pao-de-acucar", "scraper_id": "authorized-collector",
                  "schedule_id": capital["settings"]["state"].lower(),
                  "spool_path": capital["settings"]["state"] + ".sqlite3",
                  **capital["settings"]}
        lines = [name + " = " + json.dumps(value) for name, value in values.items()]
        entries.append("[[scrapers]]\n" + "\n".join(lines))
    path = tmp_path / "config.toml"
    path.write_text("\n\n".join(entries))
    return path


def test_failed_deliveries_remain_separate_for_two_capitals(tmp_path, monkeypatch):
    submissions = []
    path = write_configuration(tmp_path)
    install_mock_runtime(monkeypatch, lambda request: response(request, submissions))
    monkeypatch.setenv("INGESTION_TOKEN", "secret")
    monkeypatch.setattr(sys, "argv", ["scraper", "--config", str(path), "collect"])
    assert cli.main() == 1
    assert len(submissions) == 2
    for capital, attempted in zip(CAPITALS[:2], submissions, strict=True):
        assert_separate_spool(tmp_path, capital, attempted)
    identities = [json.loads(raw)["submission_id"] for raw in submissions]
    assert len(set(identities)) == 2


def assert_separate_spool(tmp_path, capital, attempted):
    state = capital["settings"]["state"]
    with Spool(tmp_path / (state + ".sqlite3")) as spool:
        assert next(spool.pending())[1] == attempted
    document = json.loads(attempted)
    assert document["scraper_id"] == "authorized-collector"
    contexts = [observation["context"] for observation in document["observations"]]
    assert {context["state"] for context in contexts} == {state}
    assert {context["city"] for context in contexts} == {capital["settings"]["city"]}
