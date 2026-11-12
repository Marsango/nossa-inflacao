"""Ready GBarbosa contexts reach existing VPS schedules without resetting local settings."""

import json
import tomllib
import unittest

from test_capital_settings import template, upgraded


def previous_schedule():
    return template().split("# GBarbosa verified grocery delivery contexts;")[0].rstrip() + "\n"


def gbarbosa_entries(document):
    return [entry for entry in tomllib.loads(document)["scrapers"] if entry["adapter"] == "gbarbosa"]


class GBarbosaUpgradeTests(unittest.TestCase):
    def test_existing_fifty_four_contexts_receive_three_ready_capitals(self):
        original = previous_schedule()
        updated = upgraded(original)
        entries = tomllib.loads(updated)["scrapers"]
        self.assertEqual(entries[:54], tomllib.loads(original)["scrapers"])
        additions = gbarbosa_entries(updated)
        self.assertEqual(len(entries), 57)
        self.assertEqual({entry["state"] for entry in additions}, {"SE", "BA", "AL"})
        self.assertTrue(all(entry["enabled"] for entry in additions))
        self.assertEqual(len({entry["spool_path"] for entry in entries}), 57)
        self.assertEqual(upgraded(updated), updated)

    def test_new_contexts_inherit_authorized_identity_and_connection(self):
        original = previous_schedule().replace('"muffato-curitiba-01"', '"authorized-collector"')
        original = original.replace('"http://127.0.0.1:8080"', '"https://private-core.example"')
        original = original.replace('"INGESTION_TOKEN"', '"PRIVATE_TOKEN"')
        additions = gbarbosa_entries(upgraded(original))
        self.assertEqual({entry["scraper_id"] for entry in additions}, {"authorized-collector"})
        self.assertEqual({entry["core_url"] for entry in additions}, {"https://private-core.example"})
        self.assertEqual({entry["ingestion_token_env"] for entry in additions}, {"PRIVATE_TOKEN"})


class GBarbosaPreservationTests(unittest.TestCase):
    def test_disabled_custom_context_survives_upgrade(self):
        disabled = {
            "adapter": "gbarbosa", "schedule_id": "gbarbosa-se", "enabled": False,
            "scraper_id": "custom-collector", "postal_code": "custom-preserved",
            "spool_path": "data/custom-gbarbosa.sqlite3", "timeout_seconds": 47.0,
        }
        block = "[[scrapers]]\n" + "\n".join(key + " = " + json.dumps(value)
                                             for key, value in disabled.items())
        original = previous_schedule() + block + "\n"
        updated = upgraded(original)
        entries = gbarbosa_entries(updated)
        self.assertEqual(len(entries), 3)
        selected = next(entry for entry in entries if entry["schedule_id"] == "gbarbosa-se")
        self.assertEqual(selected, disabled)
        self.assertTrue(updated.startswith(original.rstrip()))
        self.assertEqual(upgraded(updated), updated)
