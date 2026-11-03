import json
import sys
from copy import deepcopy

import httpx
from stores.test_pipeline import install_mock_runtime, monitoring_response

from inflacao_scrapers import cli
from inflacao_scrapers.delivery import Spool

from .conftest import CAPITALS, captured_products
from .test_source import branch_html


def selected_contexts():
    return [c for c in CAPITALS["contexts"] if c["settings"]["state"] in {"SP", "SC"}]


def source_response(request, fail_city):
    if request.url.path.endswith("simulation"):
        items = json.loads(request.content)["items"]
        return httpx.Response(
            200, json={"items": [{**item, "availability": "available"} for item in items]}
        )
    if request.url.host.startswith("bff-"):
        seller = request.url.params["accountName"]
        context = next(c for c in selected_contexts() if c["settings"]["seller_id"] == seller)
        return httpx.Response(200, content=json.dumps(context["directory"], default=str).encode())
    if request.url.path.startswith("/loja/"):
        context = next(
            c
            for c in selected_contexts()
            if request.url.path.endswith(c["settings"]["branch_slug"])
        )
        status = 403 if fail_city == context["settings"]["state"] else 200
        return httpx.Response(status, text=branch_html(context["branch"]))
    return product_response(request)


def product_response(request):
    variables = json.loads(request.url.params["variables"])
    facet = next(f for f in variables["selectedFacets"] if f["key"] == "channel")
    seller = json.loads(facet["value"])["seller"]
    product = deepcopy(captured_products("rice")[0])
    for offer in product["offers"]["offers"]:
        offer["seller"]["identifier"] = seller
    document = {
        "data": {
            "search": {"products": {"pageInfo": {"totalCount": 1}, "edges": [{"node": product}]}}
        }
    }
    return httpx.Response(200, content=json.dumps(document, default=str).encode())


def configuration(tmp_path):
    blocks = []
    for context in selected_contexts():
        values = {
            "adapter": "atacadao",
            "scraper_id": "authorized-collector",
            "spool_path": context["settings"]["state"] + ".sqlite3",
            **context["settings"],
        }
        blocks.append(
            "[[scrapers]]\n" + "\n".join(k + " = " + json.dumps(v) for k, v in values.items())
        )
    path = tmp_path / "config.toml"
    path.write_text("\n\n".join(blocks))
    return path


def execute(tmp_path, monkeypatch, failed_city=None, fail_delivery=False):
    submissions = []

    def respond(request):
        return response(request, submissions, failed_city, fail_delivery)

    install_mock_runtime(monkeypatch, respond)
    monkeypatch.setenv("INGESTION_TOKEN", "secret")
    path = configuration(tmp_path)
    monkeypatch.setattr(sys, "argv", ["scraper", "--config", str(path), "collect"])
    return cli.main(), submissions


def response(request, submissions, failed_city, fail_delivery):
    if request.url.host != "127.0.0.1":
        assert "authorization" not in request.headers
        return source_response(request, failed_city)
    if request.method == "GET":
        return monitoring_response()
    if request.url.path.endswith("scraper-reports"):
        return httpx.Response(201)
    if request.url.path.endswith("submissions"):
        submissions.append(request.content)
        return httpx.Response(401 if fail_delivery else 202)
    return httpx.Response(202)


def test_two_capitals_ingest_successfully_without_creating_spools(tmp_path, monkeypatch):
    status, submissions = execute(tmp_path, monkeypatch)
    assert status == 0 and len(submissions) == 2
    states = {json.loads(body)["observations"][0]["context"]["state"] for body in submissions}
    assert states == {"SC", "SP"}
    assert all(
        json.loads(body)["observations"][0]["availability"] == "in_stock" for body in submissions
    )
    assert not list(tmp_path.glob("*.sqlite3"))


def test_one_blocked_capital_does_not_prevent_the_other_ingesting(tmp_path, monkeypatch, capsys):
    status, submissions = execute(tmp_path, monkeypatch, failed_city="SC")
    assert status == 1 and len(submissions) == 1
    document = json.loads(submissions[0])
    assert document["shop_id"] == "atacadao"
    assert document["observations"][0]["context"]["state"] == "SP"
    assert not list(tmp_path.glob("*.sqlite3"))
    assert "city=Florianópolis state=SC" in capsys.readouterr().out


def test_two_capitals_keep_failed_submission_bytes_and_spools_separate(tmp_path, monkeypatch):
    status, submissions = execute(tmp_path, monkeypatch, fail_delivery=True)
    assert status == 1 and len(submissions) == 2
    for context, attempted in zip(selected_contexts(), submissions, strict=True):
        assert_saved_context(tmp_path, context, attempted)
    assert len({json.loads(body)["submission_id"] for body in submissions}) == 2


def assert_saved_context(tmp_path, context, attempted):
    state = context["settings"]["state"]
    with Spool(tmp_path / (state + ".sqlite3")) as spool:
        assert next(spool.pending())[1] == attempted
    document = json.loads(attempted)
    assert document["scraper_id"] == "authorized-collector"
    assert document["observations"][0]["context"]["state"] == state
