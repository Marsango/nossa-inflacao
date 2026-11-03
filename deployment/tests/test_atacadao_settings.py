"""Ready Atacadão contexts reach existing VPS schedules without resetting local choices."""
import tomllib
import unittest

from test_capital_settings import template, upgraded

READY_STATES = {"AC", "AL", "AM", "BA", "CE", "DF", "GO", "MA", "MG", "MS", "MT",
                "PA", "PE", "PI", "PR", "RJ", "RN", "RS", "SC", "SE", "SP", "TO"}


def original_schedule():
    return template().split("# Atacadão verified capital branches;")[0].rstrip() + "\n"


class AtacadaoUpgradeTests(unittest.TestCase):
    def test_existing_nineteen_contexts_receive_all_ready_branches(self):
        original = original_schedule()
        updated = upgraded(original)
        self.assertTrue(updated.startswith(original.rstrip()))
        entries = tomllib.loads(updated)["scrapers"]
        self.assertEqual(entries[:19], tomllib.loads(original)["scrapers"])
        additions = [entry for entry in entries[19:] if entry["adapter"] == "atacadao"]
        self.assertEqual(len(additions), 22)
        self.assertEqual({entry["state"] for entry in additions}, READY_STATES)
        self.assertTrue(all(entry["enabled"] for entry in additions))
        self.assertEqual(len({entry["schedule_id"] for entry in additions}), 22)
        self.assertEqual(len({entry["spool_path"] for entry in entries}), 54)
        self.assertEqual(upgraded(updated), updated)

    def test_custom_disabled_city_is_preserved_while_others_are_appended(self):
        original = original_schedule() + '''
[[scrapers]]
adapter = "atacadao"
schedule_id = "atacadao-sp"
enabled = false
scraper_id = "custom-authorized-collector"
branch_slug = "custom-branch"
spool_path = "data/custom-atacadao.sqlite3"
'''
        entries = tomllib.loads(upgraded(original))["scrapers"]
        additions = [entry for entry in entries if entry["adapter"] == "atacadao"]
        selected = [entry for entry in additions if entry["schedule_id"] == "atacadao-sp"]
        self.assertEqual(len(selected), 1)
        self.assertFalse(selected[0]["enabled"])
        self.assertEqual(selected[0]["spool_path"], "data/custom-atacadao.sqlite3")
        self.assertEqual(selected[0]["branch_slug"], "custom-branch")
        self.assertEqual(len(additions), 22)
        self.assertTrue(all(e["enabled"] for e in additions if e["schedule_id"] != "atacadao-sp"))


class AtacadaoIdentityTests(unittest.TestCase):
    def test_new_contexts_keep_existing_authorized_collector(self):
        original = original_schedule().replace('scraper_id = "muffato-curitiba-01"',
                                              'scraper_id = "authorized-existing-collector"')
        entries = tomllib.loads(upgraded(original))["scrapers"]
        self.assertEqual({e["scraper_id"] for e in entries}, {"authorized-existing-collector"})
