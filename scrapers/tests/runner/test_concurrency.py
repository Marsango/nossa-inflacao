from dataclasses import replace
from threading import Barrier, Event, Lock
from types import SimpleNamespace

import pytest

from inflacao_scrapers import runner


def configurations(tmp_path, workers, count=4):
    path = tmp_path / "parallel.toml"
    entries = [f'[[scrapers]]\nscraper_id="worker-{index}"\n' for index in range(count)]
    path.write_text(f"[runner]\nmax_workers={workers}\n" + "".join(entries))
    return path


@pytest.mark.parametrize("command_name", ["collect", "deliver"])
def test_workers_overlap_and_never_exceed_configured_limit(tmp_path, monkeypatch, command_name):
    active, peaks, finished = set(), [], []
    lock, barrier = Lock(), Barrier(2)

    def command(settings, arguments, adapter):
        with lock:
            active.add(settings.scraper_id)
            peaks.append(len(active))
        barrier.wait(timeout=5)
        with lock:
            active.remove(settings.scraper_id)
            finished.append(settings.scraper_id)
        return 0

    monkeypatch.setitem(runner.COMMANDS, command_name, command)
    arguments = SimpleNamespace(config=configurations(tmp_path, 2), command=command_name)
    assert runner.run(arguments) == 0
    assert max(peaks) == 2
    assert len(finished) == 4


def test_available_worker_starts_next_entry_before_slow_first_finishes(tmp_path, monkeypatch):
    completed = Event()

    def command(settings, arguments, adapter):
        if settings.scraper_id == "worker-0":
            return int(not completed.wait(timeout=5))
        if settings.scraper_id == "worker-2":
            completed.set()
        return 0

    monkeypatch.setitem(runner.COMMANDS, "collect", command)
    arguments = SimpleNamespace(config=configurations(tmp_path, 2), command="collect")
    assert runner.run(arguments) == 0
    assert completed.is_set()


def test_worker_exception_does_not_skip_queued_entries(tmp_path, monkeypatch, capsys):
    finished = []

    def command(settings, arguments, adapter):
        finished.append(settings.scraper_id)
        if settings.scraper_id == "worker-0":
            raise TypeError("private detail")
        return 0

    monkeypatch.setitem(runner.COMMANDS, "collect", command)
    arguments = SimpleNamespace(config=configurations(tmp_path, 2), command="collect")
    assert runner.run(arguments) == 1
    assert len(finished) == 4
    output = capsys.readouterr()
    assert "scrapers=4 failed=1 complete=False" in output.out
    assert "worker-0" in output.err and "Unexpected TypeError" in output.err
    assert "private detail" not in output.err


@pytest.mark.parametrize("command", ["status", "discover"])
def test_presentation_commands_remain_sequential(tmp_path, monkeypatch, command):
    finished = []
    monkeypatch.setitem(
        runner.COMMANDS, command,
        lambda settings, arguments, adapter: finished.append(settings.scraper_id) or 0,
    )
    arguments = SimpleNamespace(config=configurations(tmp_path, 2), command=command)
    assert runner.run(arguments) == 0
    assert finished == [f"worker-{index}" for index in range(4)]


def test_concurrent_diagnostics_keep_shop_and_run_identity(run_scrapers, capsys):
    execution = run_scrapers(failures={"www.supermuffato.com.br": 403})
    reports = {report["shop_id"]: report for report in execution.reports}
    assert len(reports) == 2
    assert reports["super-muffato"]["errors"] == 1
    assert reports["fixture-shop"]["errors"] == 0
    assert len({report["run_id"] for report in reports.values()}) == 2
    output = capsys.readouterr().out
    for report in reports.values():
        expected = f'run_id={report["run_id"]} scraper_id={report["scraper_id"]}'
        assert expected in output


def test_parallel_pipeline_uses_distinct_cookie_jars(run_scrapers, monkeypatch):
    from inflacao_scrapers.adapters.registry import ADAPTERS

    def prepare(requester, settings):
        client = requester.client
        assert not client.cookies
        client.cookies.set("branch", settings.shop_id)
        return settings

    for name in ("super-muffato", "fixture-shop"):
        monkeypatch.setitem(ADAPTERS, name, replace(ADAPTERS[name], prepare=prepare))
    execution = run_scrapers()
    assert execution.status == 0
    assert {client.cookies.get("branch") for client in execution.clients} == {
        "super-muffato", "fixture-shop",
    }


def test_diagnostic_failure_does_not_overwrite_another_context(run_scrapers, monkeypatch):
    from inflacao_scrapers.diagnostics import delivery

    replay = delivery.replay

    def reject_one_report(spool, requester, settings, token):
        if settings.shop_id == "super-muffato":
            raise RuntimeError("Diagnostic endpoint unavailable")
        return replay(spool, requester, settings, token)

    monkeypatch.setattr(delivery, "replay", reject_one_report)
    execution = run_scrapers()
    assert execution.status == 1
    assert [report["shop_id"] for report in execution.reports] == ["fixture-shop"]
    assert_pending_report(execution.configuration_path)


def assert_pending_report(configuration_path):
    import json

    from inflacao_scrapers.delivery import Spool

    path = configuration_path.parent / "data/super-muffato/muffato-test/spool.sqlite3.diagnostics"
    with Spool(path) as spool:
        assert spool.status()[0] == 1
        _, payload = next(spool.pending())
    assert json.loads(payload)["shop_id"] == "super-muffato"


def test_single_worker_stays_on_calling_thread(tmp_path, monkeypatch):
    from threading import get_ident

    threads = []
    monkeypatch.setitem(
        runner.COMMANDS, "collect",
        lambda *arguments: threads.append(get_ident()) or 0,
    )
    arguments = SimpleNamespace(config=configurations(tmp_path, 1), command="collect")
    assert runner.run(arguments) == 0
    assert threads == [get_ident()] * 4
