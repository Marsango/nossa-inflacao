"""Bounded completed-run reports with retailer display names."""

import json
from datetime import UTC, datetime

NAMES = {
    "mambo": "Mambo",
    "festval": "Festval",
    "angeloni": "Angeloni",
    "super-muffato": "Super Muffato",
    "hirota": "Hirota",
    "nagumo": "Nagumo",
    "sonda": "Sonda",
    "pao-de-acucar": "Pão de Açúcar",
}


def display_name(adapter):
    return NAMES.get(adapter, adapter.replace("-", " ").title())


def encode_report(run, settings, token=""):
    report = {
        "schema_version": "1.0",
        "scraper_id": settings.scraper_id,
        "shop_id": settings.shop_id,
        "run_id": str(run.identity),
        "scraper_name": display_name(settings.adapter),
        "started_at": run.started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "observations": run.observations,
        "errors": run.failures,
        "warnings": run.warnings,
        "omitted": run.failures + run.warnings - len(run.diagnostics),
        "diagnostics": sanitized_entries(run.diagnostics, token),
    }
    return bounded_report(report)


def bounded_report(report):
    payload = json.dumps(report, ensure_ascii=False).encode()
    while len(payload) > 256 * 1024:
        report["diagnostics"].pop(discard_index(report["diagnostics"]))
        report["omitted"] += 1
        payload = json.dumps(report, ensure_ascii=False).encode()
    return payload


def record(run, severity, message):
    entry = {
        "severity": severity,
        "category": "collection",
        "message": str(message)[:2000] or "Unspecified collection issue",
    }
    if entry in run.diagnostics:
        return
    if len(run.diagnostics) < 100:
        run.diagnostics.append(entry)
        return
    index = discard_index(run.diagnostics)
    if severity == "error" and run.diagnostics[index]["severity"] == "warning":
        run.diagnostics.pop(index)
        run.diagnostics.append(entry)


def discard_index(entries):
    warnings = [index for index, entry in enumerate(entries) if entry["severity"] == "warning"]
    if warnings:
        return warnings[-1]
    return len(entries) - 1


def sanitized_entries(entries, token):
    if not token:
        return list(entries)
    return [
        {**entry, "message": entry["message"].replace(token, "[redacted]")} for entry in entries
    ]
