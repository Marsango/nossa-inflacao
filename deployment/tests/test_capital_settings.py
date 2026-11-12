"""Upgrade existing schedules without replacing collector credentials or local choices."""
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

import lifecycle
import settings
from test_settings import EXISTING, synchronize


def template():
    return (settings.ROOT / "scrapers/scrapers.example.toml").read_text()


def upgraded(original):
    with tempfile.TemporaryDirectory() as directory:
        return synchronize(directory, original)


class CapitalUpgradeTests(unittest.TestCase):
    def test_eight_existing_collectors_receive_ready_capital_contexts(self):
        original = template().split("# Additional state capitals;")[0].rstrip() + "\n"
        updated = upgraded(original)
        entries = tomllib.loads(updated)["scrapers"]
        self.assertTrue(updated.startswith(original.rstrip()))
        self.assertEqual(len(entries), 57)
        self.assertEqual(entries[:8], tomllib.loads(original)["scrapers"])
        self.assertTrue(all(entry["enabled"] for entry in entries[8:]))
        self.assertEqual(len({entry["spool_path"] for entry in entries}), 57)
        self.assertEqual(upgraded(updated), updated)

    def test_customized_disabled_capital_is_not_duplicated_or_reenabled(self):
        original = EXISTING + '''
[[scrapers]]
adapter = "pao-de-acucar"
schedule_id = "pao-de-acucar-rj"
enabled = false
scraper_id = "custom-collector"
city = "Custom address"
postal_code = "22031000"
spool_path = "data/custom-rio.sqlite3"
'''
        updated = upgraded(original)
        self.assertTrue(updated.startswith(original.rstrip()))
        entries = tomllib.loads(updated)["scrapers"]
        matches = [entry for entry in entries if entry.get("schedule_id") == "pao-de-acucar-rj"]
        self.assertEqual(len(matches), 1)
        self.assertFalse(matches[0]["enabled"])
        self.assertEqual(matches[0]["spool_path"], "data/custom-rio.sqlite3")


class CollectorIdentityTests(unittest.TestCase):
    def test_additions_inherit_existing_collector_and_connection_settings(self):
        original = EXISTING.replace('scraper_id = "muffato-curitiba-01"', '''
scraper_id = "authorized-collector"
core_url = "https://private-core.example"
ingestion_token_env = "PRIVATE_INGESTION_TOKEN"'''.strip())
        entries = tomllib.loads(upgraded(original))["scrapers"]
        for entry in entries:
            self.assertEqual(entry["scraper_id"], "authorized-collector")
            self.assertEqual(entry["core_url"], "https://private-core.example")
            self.assertEqual(entry["ingestion_token_env"], "PRIVATE_INGESTION_TOKEN")

    def test_first_install_and_repeated_upgrade_keep_the_template(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(settings, "CONFIG", Path(directory)),
        ):
            settings.initialize()
            settings.synchronize_scrapers()
            settings.synchronize_scrapers()
            actual = (Path(directory) / "scrapers.toml").read_text()
        self.assertEqual(actual, template())

    def test_all_scheduled_retailers_are_registered_and_authorized(self):
        entries = tomllib.loads(template())["scrapers"]
        shops = {entry.get("shop_id", entry["adapter"]) for entry in entries}
        compose = (settings.ROOT / "deployment/compose.yaml").read_text()
        line = next(line.strip() for line in compose.splitlines()
                    if line.strip().startswith("INGESTION_SHOP_IDS:"))
        authorized = line.split(":", 1)[1].strip()
        self.assertLessEqual(shops, set(authorized.split(",")))
        for shop in shops:
            self.assertIn("('" + shop + "',", lifecycle.SHOPS)
