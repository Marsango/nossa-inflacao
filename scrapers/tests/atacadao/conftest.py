from copy import deepcopy
from pathlib import Path

import pytest

from inflacao_scrapers.atacadao.config import AtacadaoSettings
from inflacao_scrapers.vtex.json import decode_response

FIXTURES = Path(__file__).parents[1] / "fixtures/stores"
CAPITALS = decode_response((FIXTURES / "atacadao-capitals.json").read_bytes())


def configuration(context):
    return AtacadaoSettings(scraper_id="authorized-collector", **context["settings"])


def captured_products(name):
    raw = (FIXTURES / f"atacadao-{name}.json").read_bytes()
    document = decode_response(raw)
    return [edge["node"] for edge in document["data"]["search"]["products"]["edges"]]


@pytest.fixture(params=CAPITALS["contexts"], ids=lambda context: context["settings"]["state"])
def capital(request):
    return deepcopy(request.param)


@pytest.fixture
def settings():
    selected = next(c for c in CAPITALS["contexts"] if c["settings"]["state"] == "SP")
    result = configuration(selected)
    result.verify_context()
    return result
