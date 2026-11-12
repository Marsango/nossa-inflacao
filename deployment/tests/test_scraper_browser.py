"""Read-only runtime smoke using disposable Testcontainers, never application databases."""
import json
import os
from pathlib import Path

import pytest


def test_parallel_runner_resources_and_browser_isolation(scraper_browser):
    script = Path(__file__).with_name("parallel_runtime.py").read_text()
    results = [runner_measurement(scraper_browser, script, workers) for workers in (1, 2)]
    print(json.dumps(results, indent=2))
    assert [result["workers"] for result in results] == [1, 2]
    assert all(result["peak_browsers"] == 1 for result in results)


def runner_measurement(container, script, workers):
    exit_code, output = container.exec(["python", "-c", script, str(workers)])
    assert exit_code == 0, output.decode()
    lines = output.decode().splitlines()
    metrics = next(line.removeprefix("RUNTIME_METRICS ") for line in lines
                   if line.startswith("RUNTIME_METRICS "))
    return json.loads(metrics)


def test_browser_starts_as_collector_without_cache_or_exports(scraper_browser):
    script = """
from botasaurus.browser import browser
@browser(headless=True,cache=False,output=None,raise_exception=True,max_retry=0,
         create_error_logs=False,chrome_executable_path='/usr/bin/chromium')
def check(driver, data):
    driver.get('data:text/html,<title>runtime-ok</title><p>Anonymous browser runtime</p>')
    assert driver.run_js('return document.title') == 'runtime-ok'
check(None)
"""
    exit_code, output = scraper_browser.exec(["python", "-c", script])
    assert exit_code == 0, output.decode()


@pytest.mark.skipif(os.environ.get("NOSSA_LIVE_SHOPS") != "1", reason="Set NOSSA_LIVE_SHOPS=1")
def test_live_hirota_extraction_in_deployment_runtime(scraper_browser):
    script = """
from inflacao_scrapers.commands import create_client, create_requester
from inflacao_scrapers.hirota.adapter import ADAPTER
from inflacao_scrapers.hirota.config import HirotaSettings
settings = HirotaSettings(scraper_id='diagnostic-sp')
with create_client(settings) as client:
    requester = create_requester(client, settings)
    settings = ADAPTER.prepare(requester, settings)
    page = ADAPTER.discover(requester, settings, 'leite', 1)
assert not page.issues and len(page.observations) == 1
assert page.observations[0].context.postal_code == '04263100'
assert page.observations[0].offers
"""
    exit_code, output = scraper_browser.exec(["python", "-c", script])
    assert exit_code == 0, output.decode()
