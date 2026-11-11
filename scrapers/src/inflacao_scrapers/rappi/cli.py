"""Inspect public Rappi directories and product previews; never schedule or submit them."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import httpx

from ..commands import create_client, create_requester
from ..config import Settings
from ..scope import MonitoringTarget
from .catalog import parse_storefront
from .directory import parse_directory
from .document import ORIGIN, public_url
from .parsing import parse_observations
from .source import Capture, fetch_page


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    add_directory_arguments(commands)
    add_inspection_arguments(commands)
    return parser


def add_directory_arguments(commands):
    directory = commands.add_parser("directory", help="List branches; default skips existing retailers")
    directory.add_argument("--url", default=ORIGIN + "/lojas/tipo/supermercados")
    directory.add_argument("--include-existing", action="store_true")
    add_source_arguments(directory)


def add_inspection_arguments(commands):
    inspect = commands.add_parser("inspect", help="Parse a branch/category preview without submitting")
    inspect.add_argument("--url", required=True)
    inspect.add_argument("--store-id", help="Require the expected Rappi branch ID")
    inspect.add_argument("--query", help="Filter displayed products locally")
    add_source_arguments(inspect)


def add_source_arguments(command):
    command.add_argument("--input", type=Path, help="Read saved HTML instead of fetching")
    command.add_argument("--observed-at", type=timestamp, help="Original UTC/offset capture time")


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError("Timezone required")
        return result
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected an ISO timestamp with timezone") from error


def capture(arguments):
    public_url(arguments.url)
    if arguments.input is not None:
        return saved_capture(arguments)
    if arguments.observed_at is not None:
        raise ValueError("Live Rappi requests use the actual fetch time; omit --observed-at")
    settings = Settings(scraper_id="rappi-inspection", shop_id="rappi", shop_url=ORIGIN)
    with create_client(settings) as client:
        return fetch_page(create_requester(client, settings), arguments.url)


def saved_capture(arguments):
    if arguments.observed_at is None:
        raise ValueError("Saved Rappi HTML requires its original --observed-at timestamp")
    return Capture(arguments.input.read_text(), arguments.observed_at)


def inspection_report(source, arguments):
    storefront = parse_storefront(source.source, arguments.url, arguments.store_id)
    page = parse_observations(
        storefront, arguments.url, source.observed_at, query_target(arguments.query)
    )
    branch = storefront.branch
    return {
        "source_url": arguments.url, "channel": "rappi", "ready_for_collection": False,
        "branch": {key: branch.get(key) for key in ("name", "store_id", "city", "address")},
        "coverage": storefront.coverage(), "membership_required": storefront.membership_required,
        "observations": [item.model_dump(mode="json") for item in page.observations],
        "issues": page.issues, "warnings": page.warnings,
    }


def query_target(query):
    if query is None:
        return None
    return MonitoringTarget(
        id="inspection", name=query, search_queries=[query],
        required_terms=[[query]], excluded_terms=[],
    )


def report(arguments):
    source = capture(arguments)
    if arguments.command == "directory":
        result = parse_directory(source.source).report(arguments.include_existing)
        return {**capture_metadata(source, arguments), **result}
    return {**capture_metadata(source, arguments), **inspection_report(source, arguments)}


def capture_metadata(source, arguments):
    return {
        "source_url": arguments.url, "observed_at": source.observed_at.isoformat(),
        "replayed": arguments.input is not None, "cache": source.cache,
    }


def main(argv=None):
    arguments = argument_parser().parse_args(argv)
    try:
        result = report(arguments)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(bool(result.get("issues")))
    except (ValueError, RuntimeError, OSError, httpx.HTTPError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
