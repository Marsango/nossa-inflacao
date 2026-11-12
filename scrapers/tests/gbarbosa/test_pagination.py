import httpx
import pytest

from inflacao_scrapers.gbarbosa.adapter import ADAPTER
from inflacao_scrapers.transport import Requester

from .conftest import encode


def test_registered_adapter_completes_search_using_source_offsets(capture, prepared):
    offsets = []

    def handler(request):
        offset = int(request.url.params["_from"])
        offsets.append(offset)
        assert request.url.params["regionId"] == prepared.region_id
        products = capture["products"][offset : min(offset + 2, 3)]
        return httpx.Response(
            206,
            content=encode(products),
            headers={"resources": f"{offset}-{offset + len(products) - 1}/3"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        pages = list(ADAPTER.search_pages(Requester(client, interval=0), prepared, None, "arroz"))
    assert offsets == [0, 2]
    assert sum(len(page.observations) for page in pages) == 3
    assert not any(page.issues for page in pages)


def test_repeated_search_page_fails_instead_of_claiming_completion(capture, prepared):
    def handler(request):
        return httpx.Response(
            206, content=encode(capture["products"][:2]), headers={"resources": "0-1/4"}
        )

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="repeated SKU page"),
    ):
        list(ADAPTER.search_pages(Requester(client, interval=0), prepared, None, "arroz"))


def test_explicit_search_budget_reports_incomplete_collection(capture, prepared):
    def handler(request):
        return httpx.Response(
            206, content=encode(capture["products"][:2]), headers={"resources": "0-1/4"}
        )

    prepared.max_search_pages = 1
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="page limit reached"),
    ):
        list(ADAPTER.search_pages(Requester(client, interval=0), prepared, None, "arroz"))
