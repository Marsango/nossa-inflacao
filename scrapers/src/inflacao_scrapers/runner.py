"""Run each enabled scraper in isolation and report an aggregate exit status."""

import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
from time import monotonic

import httpx

from .adapters.registry import registered_adapter
from .commands import COMMANDS
from .config import load_runner
from .execution.output import write_line


def run(arguments) -> int:
    runner, configurations = load_runner(arguments.config)
    workers = min(runner.max_workers, len(configurations))
    if arguments.command not in ("collect", "deliver"):
        workers = min(1, workers)
    write_line(f"command={arguments.command} workers={workers}", flush=True)
    results = execute_scrapers(configurations, arguments, workers)
    failures = sum(result != 0 for result in results)
    write_line(f"scrapers={len(results)} failed={failures} complete={failures == 0}", flush=True)
    return int(failures != 0)


def execute_scrapers(configurations, arguments, workers) -> list[int]:
    if workers <= 1:
        return [run_scraper(settings, arguments) for settings in configurations]
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="scraper")
    try:
        return list(executor.map(run_scraper, configurations, repeat(arguments)))
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def run_scraper(settings, arguments) -> int:
    started = monotonic()
    write_line(
        f"{scraper_context(settings)} command={arguments.command}",
        flush=True,
    )
    result = execute_command(settings, arguments)
    write_line(
        f"{scraper_context(settings)} exit_status={result} "
        f"elapsed_seconds={monotonic() - started:.3f}", flush=True,
    )
    return result


def execute_command(settings, arguments) -> int:
    try:
        adapter = registered_adapter(settings.adapter)
        command = COMMANDS[arguments.command]
        return command(settings, arguments, adapter)
    except httpx.HTTPError:
        return report_failure(settings, "HTTP request failed")
    except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
        return report_failure(settings, str(error))
    except Exception as error:
        error_name = type(error).__name__
        return report_failure(settings, f"Unexpected {error_name} during scraper execution")


def report_failure(settings, message: str) -> int:
    write_line(
        f"{scraper_context(settings)}: {message}", file=sys.stderr, flush=True,
    )
    return 1


def scraper_context(settings) -> str:
    return (
        f"scraper_id={settings.scraper_id} shop_id={settings.shop_id} "
        f"adapter={settings.adapter} schedule_id={settings.schedule_id or 'default'}"
    )
