"""Durable bounded diagnostic delivery using a separate SQLite spool."""

import sys

from ..delivery.spool import Spool
from ..execution.output import write_line
from .report import encode_report


def diagnostic_spool(settings, arguments):
    path = arguments.config.parent / settings.spool_path
    return Spool(path.with_name(path.name + ".diagnostics"), settings.spool_capacity_bytes)


def replay(spool, requester, settings, token):
    for identity, payload in spool.pending():
        response = requester.request(
            "POST", settings.core_url + "/api/v1/ingestion/scraper-reports",
            content=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        if response.status_code not in (200, 201) or response.content:
            raise RuntimeError(f"Diagnostic report rejected: HTTP {response.status_code}")
        spool.acknowledge(identity)


def try_replay(spool, requester, settings, token):
    try:
        replay(spool, requester, settings, token)
        return True
    except Exception:
        report_failure(settings, "Diagnostic delivery failed; reports retained for retry")
        return False


def complete(spool, requester, settings, token, run):
    try:
        payload = encode_report(run, settings, token)
        spool.enqueue_payload(str(run.identity), payload)
    except Exception:
        report_failure(settings, "Diagnostic queue unavailable or full; report could not be saved")
        return False
    return try_replay(spool, requester, settings, token)


def report_failure(settings, message):
    write_line(
        f"scraper_id={settings.scraper_id} shop_id={settings.shop_id} "
        f"schedule_id={settings.schedule_id or 'default'}: {message}",
        file=sys.stderr, flush=True,
    )
