import json
import sys

import httpx
from stores.test_pipeline import install_mock_runtime

from inflacao_scrapers import cli
from inflacao_scrapers.delivery import Spool
from inflacao_scrapers.models import Submission

from .conftest import encode, selected_product


def scope_response():
    target = dict(
        id="arroz",
        name="Arroz",
        search_queries=["arroz"],
        required_terms=[["arroz"]],
        excluded_terms=[],
    )
    return httpx.Response(200, json={"schema_version": "1.0", "targets": [target]})


def response(request, capture, submissions, failed):
    if request.url.host != "127.0.0.1":
        return source_response(request, capture)
    assert request.headers["authorization"] == "Bearer secret"
    if request.method == "GET":
        return scope_response()
    if request.url.path.endswith("submissions"):
        submissions.append(request.content)
        return httpx.Response(401 if failed else 202)
    return httpx.Response(201)


def source_response(request, capture):
    assert "authorization" not in request.headers
    if request.url.path.endswith("/regions"):
        return httpx.Response(200, content=encode(capture["regions"]))
    assert request.url.params["regionId"] == capture["regions"][0]["id"]
    assert "vtex_segment=" in request.headers["cookie"]
    return httpx.Response(
        206, content=encode([selected_product(capture)]), headers={"resources": "0-0/1"}
    )


def execute(tmp_path, monkeypatch, capture, failed=False):
    submissions = []

    def handler(request):
        return response(request, capture, submissions, failed)

    fields = {key: capture[key] for key in ("city", "state", "postal_code", "regional_seller_id")}
    values = dict(
        adapter="gbarbosa",
        scraper_id="authorized-collector",
        spool_path="gbarbosa.sqlite3",
        **fields,
    )
    path = tmp_path / "config.toml"
    path.write_text("\n".join(key + " = " + json.dumps(value) for key, value in values.items()))
    monkeypatch.setenv("INGESTION_TOKEN", "secret")
    install_mock_runtime(monkeypatch, handler)
    monkeypatch.setattr(sys, "argv", ["scraper", "--config", str(path), "collect"])
    return cli.main(), submissions


def test_collect_delivers_valid_contract_and_preserves_provenance(tmp_path, monkeypatch, capture):
    status, documents = execute(tmp_path, monkeypatch, capture)
    assert status == 0
    assert len(documents) == 1
    submission = Submission.model_validate_json(documents[0])
    assert submission.scraper_id == "authorized-collector"
    assert submission.shop_id == submission.collector.name == "gbarbosa"
    context = submission.observations[0].context
    assert context.city == capture["city"]
    assert context.postal_code == capture["postal_code"]
    assert not list(tmp_path.rglob("*.sqlite3"))


def test_failed_delivery_retains_the_exact_payload_for_retry(tmp_path, monkeypatch, capture):
    status, documents = execute(tmp_path, monkeypatch, capture, failed=True)
    assert status == 1
    with Spool(tmp_path / "gbarbosa.sqlite3") as spool:
        pending = list(spool.pending())
    assert len(pending) == 1
    assert pending[0][1] == documents[0]
