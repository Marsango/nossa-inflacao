from decimal import Decimal

import pytest

from inflacao_scrapers.carrefour.decoding import ReferenceTable

from .conftest import FIXTURES, captured_search


def test_source_decimal_tokens_remain_exact_in_both_real_contexts():
    for state in ["SP", "RJ"]:
        products = captured_search(state)["products"]
        price = products[0]["items"][0]["bestSeller"]["commertialOffer"]["Price"]
        assert type(price) is Decimal
    raw = (FIXTURES / "carrefour-sp.data").read_text()
    assert "6.59" in raw


def test_null_and_undefined_remain_explicitly_unknown():
    assert ReferenceTable('[{"_1":-5,"_2":-7},"null","undefined"]').resolve() == {
        "null": None,
        "undefined": None,
    }


@pytest.mark.parametrize(
    "raw",
    [
        "<html>Captcha</html>",
        "[]",
        "{}",
        '[{"_1":0},"cycle"]',
        '[{"_1":99},"bad"]',
        '[{"_1":-2},"notANumber"]',
        '[{"_1":true},"booleanRef"]',
        '[{"_1":2,"_1":3},"duplicate",0,1]',
        '[{"_1":3,"_2":3},"duplicate","duplicate",1]',
        '[{"_1":2},"price",NaN]',
        '[{"_1":2},"date",["D",123]]',
    ],
)
def test_malformed_challenged_nonfinite_and_unsupported_source_fails(raw):
    with pytest.raises((ValueError, TypeError)):
        ReferenceTable(raw).resolve()


def test_missing_search_route_does_not_succeed_as_an_empty_catalog():
    with pytest.raises(ValueError, match="route absent"):
        ReferenceTable('[{"_1":2},"root",{}]').route("routes/busca.$term")
