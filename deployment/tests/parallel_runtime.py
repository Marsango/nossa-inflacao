"""Offline worker/resource smoke, executed inside the disposable scraper container."""

import json
import resource
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic, sleep
from types import SimpleNamespace

import httpx
import psutil
from inflacao_scrapers import runner
from inflacao_scrapers.carrefour import session
from inflacao_scrapers.transport import Requester


def snapshot():
    process = psutil.Process()
    processes = [process] + process.children(recursive=True)
    values = [process_resources(child) for child in processes]
    return tuple(sum(value[index] for value in values) for index in range(3))


def process_resources(process):
    try:
        arguments = process.cmdline()
        debug_port = any(value.startswith("--remote-debugging-port=") for value in arguments)
        subprocess = any(value.startswith("--type=") for value in arguments)
        browser = debug_port and not subprocess
        memory = process.memory_info()
        return memory.rss, process.num_fds(), int(browser)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0, 0, 0


def monitor_resources(stopped, peaks):
    while not stopped.is_set():
        values = snapshot()
        peaks[:] = [max(previous, value) for previous, value in zip(peaks, values, strict=True)]
        stopped.wait(0.05)


def initialize_browser(driver, settings):
    driver.get("data:text/html,<title>isolated</title><p>offline browser</p>")
    assert driver.run_js("return window.name") == ""
    driver.run_js("window.name = args.identity", {"identity": settings.schedule_id})


def browser_work(settings):
    with session.open_session(settings) as driver:
        configuration = driver.config
        profile = Path(configuration.profile_directory)
        sleep(1.2)
        assert driver.run_js("return window.name") == settings.schedule_id
    assert not profile.exists(), "Browser profile leaked"


def api_work(settings):
    with httpx.Client(transport=httpx.MockTransport(source_response)) as client:
        assert not client.cookies
        client.cookies.set("branch", settings.schedule_id)
        requester = Requester(client, attempts=1, interval=0.4)
        for _ in range(4):
            requester.request("GET", "https://fixture.example/products")
        assert client.cookies.get("branch") == settings.schedule_id


def source_response(request):
    return httpx.Response(200, content=b"x" * 1024 * 1024)


def collect(settings, arguments, adapter):
    if settings.adapter == "carrefour":
        browser_work(settings)
        return 0
    api_work(settings)
    return 0


def configuration(directory, workers):
    adapters = ["super-muffato", "carrefour"] + ["super-muffato"] * 4
    adapters += ["carrefour", "super-muffato"]
    entries = [configuration_entry(index, adapter) for index, adapter in enumerate(adapters)]
    path = Path(directory) / "scrapers.toml"
    path.write_text(f"[runner]\nmax_workers={workers}\n" + "".join(entries))
    return path


def configuration_entry(index, adapter):
    result = (
        f'[[scrapers]]\nadapter="{adapter}"\nscraper_id="runtime-test"\n'
        f'schedule_id="entry-{index}"\nspool_path="data/entry-{index}.sqlite3"\n'
    )
    if adapter == "carrefour":
        result += 'chrome_executable_path="/usr/bin/chromium"\n'
    return result


def measure(workers):
    stopped, peaks = Event(), [0, 0, 0]
    monitor = Thread(target=monitor_resources, args=(stopped, peaks))
    monitor.start()
    started = monotonic()
    try:
        with TemporaryDirectory() as directory:
            arguments = SimpleNamespace(config=configuration(directory, workers), command="collect")
            assert runner.run(arguments) == 0
    finally:
        stopped.set()
        monitor.join()
    return metrics(workers, started, peaks)


def metrics(workers, started, peaks):
    usage = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = usage.ru_utime + usage.ru_stime + children.ru_utime + children.ru_stime
    assert peaks[2] == 1, f"Expected one active browser, measured {peaks[2]}"
    assert snapshot()[2] == 0, "Browser process leaked"
    return {
        "workers": workers, "elapsed_seconds": round(monotonic() - started, 3),
        "cpu_seconds": round(cpu, 3), "peak_process_tree_rss_mib": round(peaks[0] / 1048576, 1),
        "peak_process_tree_file_descriptors": peaks[1], "peak_browsers": peaks[2],
    }


if __name__ == "__main__":
    runner.COMMANDS["collect"] = collect
    session.initialize_context = initialize_browser
    print("RUNTIME_METRICS " + json.dumps(measure(int(sys.argv[1]))), flush=True)
