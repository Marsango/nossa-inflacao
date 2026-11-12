"""Verified Carrefour capitals reach persisted VPS schedules without resetting local choices."""

import tomllib
import unittest

from test_capital_settings import template, upgraded

READY_STATES = {"SP", "RJ", "AM", "DF", "ES", "GO", "MG", "MS", "PB", "PE", "PR", "RN", "SC"}


def previous_schedule():
    return template().split("# Carrefour verified delivery regions;")[0].rstrip() + "\n"


def previous_two_capitals():
    return template().split("# Additional verified Carrefour capital delivery regions.")[0].rstrip() + "\n"


class CarrefourUpgradeTests(unittest.TestCase):
    def test_existing_forty_one_contexts_receive_all_verified_carrefour_capitals(self):
        original = previous_schedule()
        updated = upgraded(original)
        entries = tomllib.loads(updated)["scrapers"]
        self.assertTrue(updated.startswith(original.rstrip()))
        self.assertEqual(entries[:41], tomllib.loads(original)["scrapers"])
        additions = [entry for entry in entries[41:] if entry["adapter"] == "carrefour"]
        self.assertEqual({entry["state"] for entry in additions}, READY_STATES)
        self.assertTrue(all(entry["enabled"] for entry in additions))
        self.assertEqual(len({entry["spool_path"] for entry in entries}), 57)
        self.assertEqual(upgraded(updated), updated)

    def test_upgrade_preserves_explicit_disable_custom_settings_and_collector(self):
        original = previous_schedule().replace('"muffato-curitiba-01"', '"authorized-collector"')
        original += '''
[[scrapers]]
adapter = "carrefour"
schedule_id = "carrefour-sp"
enabled = false
scraper_id = "authorized-collector"
spool_path = "data/custom-carrefour.sqlite3"
timeout_seconds = 47.0
'''
        entries = tomllib.loads(upgraded(original))["scrapers"]
        contexts = [entry for entry in entries if entry["adapter"] == "carrefour"]
        self.assertEqual(len(contexts), 13)
        self.assertFalse(contexts[0]["enabled"])
        self.assertEqual(contexts[0]["timeout_seconds"], 47.0)
        self.assertEqual(contexts[0]["spool_path"], "data/custom-carrefour.sqlite3")
        self.assertEqual({entry["scraper_id"] for entry in contexts}, {"authorized-collector"})


class CarrefourCapitalUpgradeTests(unittest.TestCase):
    def test_existing_sao_paulo_and_rio_survive_while_eleven_missing_capitals_are_added(self):
        original = previous_two_capitals()
        entries = tomllib.loads(upgraded(original))["scrapers"]
        self.assertEqual(entries[:43], tomllib.loads(original)["scrapers"])
        additions = [entry for entry in entries[43:] if entry["adapter"] == "carrefour"]
        self.assertEqual({entry["state"] for entry in additions}, READY_STATES - {"SP", "RJ"})
        self.assertTrue(all(entry["enabled"] for entry in entries[43:]))
        self.assertEqual({entry["scraper_id"] for entry in entries}, {"muffato-curitiba-01"})
        self.assertEqual(len({entry["spool_path"] for entry in entries}), 57)

    def test_new_capital_explicit_disable_is_not_reenabled_or_duplicated(self):
        original = previous_two_capitals() + '''
[[scrapers]]
adapter = "carrefour"
schedule_id = "carrefour-mg"
enabled = false
scraper_id = "muffato-curitiba-01"
postal_code = "custom-preserved"
spool_path = "data/custom-bh.sqlite3"
'''
        entries = tomllib.loads(upgraded(original))["scrapers"]
        selected = [entry for entry in entries if entry.get("schedule_id") == "carrefour-mg"]
        self.assertEqual(len(selected), 1)
        self.assertFalse(selected[0]["enabled"])
        self.assertEqual(selected[0]["postal_code"], "custom-preserved")
        self.assertEqual(selected[0]["spool_path"], "data/custom-bh.sqlite3")
