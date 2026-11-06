"""Officials that live in sibling repositories (docs/PLUGINS.md): what the venue accepts from a plug-in.

A plug-in is trusted code, and its answer is still checked: anything missing, malformed or out of vocabulary is
`unverified`, never `pass`.

    python -B -m unittest tests.test_plugins -v
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from barclays.canon import read_json, write_json  # noqa: E402
from barclays.errors import BarclaysError, Refusal  # noqa: E402
from barclays.ledger import audit  # noqa: E402
from barclays.officials import external  # noqa: E402
from barclays.runner import _load, open_run, run_bout, write_manifest  # noqa: E402
from barclays.weighin import run_weigh_in  # noqa: E402

EVENTS = os.path.join(ROOT, "events")
FIX = os.path.join(ROOT, "fixtures")
STUB = os.path.join(ROOT, "tests", "assets", "stub_plugin.py")


class PluginOfficials(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bc-plugin-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(os.environ.pop, "BARCLAYS_PLUGINS", None)
        self.addCleanup(os.environ.pop, "FAKE_ROUTE_API_KEY", None)
        os.environ.pop("BARCLAYS_PLUGINS", None)
        # An event that names one official this repository does not contain.
        self.events = os.path.join(self.tmp, "events")
        os.makedirs(self.events)
        card = read_json(os.path.join(EVENTS, "editorial-revision.json"))
        card.update(event_id="stub-event", status="officials_runnable", stages=["weigh_in", "human_review"])
        card["officials"] = [{"id": "stub", "official": "stub.check", "authority": "disqualify", "applies_to": "all",
                              "params": {"mode": "fail_on_word", "word": "ZZZ-not-in-any-candidate"},
                              "why": "test"}]
        self.card_path = os.path.join(self.events, "stub-event.json")
        write_json(self.card_path, card)
        self.bout_dir = os.path.join(self.tmp, "bout")
        shutil.copytree(os.path.join(FIX, "editorial-clear-win"), self.bout_dir)
        bout = read_json(os.path.join(self.bout_dir, "bout.json"))
        bout["event"] = "stub-event"
        write_json(os.path.join(self.bout_dir, "bout.json"), bout)

    def table(self, **spec):
        entry = {"argv": [sys.executable, STUB, "stub.check"], "repo": "test-stub",
                 "allowed_sensitivity": ["synthetic", "public"], "timeout_seconds": 20}
        entry.update(spec)
        path = os.path.join(self.tmp, f"plugins-{len(os.listdir(self.tmp))}.json")
        write_json(path, {"schema": "barclays.plugins/0.1", "officials": {"stub.check": entry}})
        os.environ["BARCLAYS_PLUGINS"] = path
        return path

    def mode(self, mode, **params):
        card = read_json(self.card_path)
        card["officials"][0]["params"] = dict({"mode": mode}, **params)
        write_json(self.card_path, card)

    def weigh(self):
        bout, event = _load(self.bout_dir, self.events)
        out = os.path.join(self.tmp, f"run-{len(os.listdir(self.tmp))}")
        ledger = open_run(out)
        write_manifest(bout, event, ledger, out)
        return run_weigh_in(bout, event, out, ledger), out

    def test_a_plugin_result_is_an_official_result_like_any_other(self):
        self.table()
        self.mode("fail_on_word", word="encouraging")       # every candidate in this fixture carries the word
        wi, out = self.weigh()
        res = wi["results"][0]
        self.assertEqual((res["official"], res["official_version"], res["status"]), ("stub.check", "9.9", "fail"))
        self.assertEqual(res["findings"][0]["id"], "WORD-1")
        self.assertEqual(res["leads"][0]["basis"], "heuristic")
        self.assertEqual(res["receipt"]["plugin_receipt"], {"stub": True})
        self.assertRegex(res["receipt"]["entry_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(all(e["status"] == "disqualified" for e in wi["eligibility"].values()))
        # The request carried the bout's sources, and the scratch directory is gone from the run.
        self.assertIn("source_draft", res["metrics"]["sources_seen"])
        self.assertFalse([n for n in os.listdir(out) if n.startswith("weighin-")])
        self.assertIn("plugins", read_json(os.path.join(out, "manifest.json")))

    def test_a_plugin_never_sees_a_credential_shaped_variable(self):
        os.environ["FAKE_ROUTE_API_KEY"] = "not-a-real-key"
        self.table()
        self.mode("pass")
        wi, _ = self.weigh()
        self.assertEqual(wi["results"][0]["status"], "pass")
        self.assertEqual(wi["results"][0]["metrics"]["secret_like_env_names"], [])
        # Nor the venue's own settings (where the plug-in table and the controller are), nor a path in the run.
        self.assertEqual(wi["results"][0]["metrics"]["venue_env_names"], [])
        self.assertNotIn(self.tmp, wi["results"][0]["metrics"]["workdir"])

    def test_a_table_rewritten_in_mid_run_changes_nothing_and_is_flagged(self):
        # Fourth review, R4-02: a plug-in rewrote the table it was listed in, later calls went to the new entry,
        # and the manifest still named the old one.
        table = self.table()
        self.mode("rewrite_table", table_path=table, word="encouraging")
        verdict = run_bout(self.bout_dir, os.path.join(self.tmp, "out"), self.events)
        statuses = {e["status"] for e in verdict["eligibility"].values()}
        self.assertEqual(statuses, {"disqualified"})          # every call still went to the pinned entry
        self.assertIn("PLUGIN_TABLE_CHANGED_DURING_RUN", verdict["flags"])
        self.assertIn("FORCE_PASS", read_json(table)["officials"]["stub.check"]["argv"])   # it really was rewritten

    def test_a_file_planted_in_the_run_is_named_by_the_seal(self):
        # R4-04. A plug-in is trusted code and can still write where it should not. The file is sealed with the
        # rest, and the audit says the venue did not write it.
        self.table()
        out = os.path.join(self.tmp, "out")
        self.mode("plant_file", plant_in=out)
        verdict = run_bout(self.bout_dir, out, self.events)
        report = audit(out, verdict["_ledger_head"])
        self.assertTrue(report["consistent"])
        self.assertTrue(any("did not write" in w and "PLANTED.txt" in w for w in report["warnings"]))

    def test_anything_but_a_valid_answer_is_unverified_never_pass(self):
        self.table(timeout_seconds=1)
        for mode in ("exit3", "garbage", "no_response", "fail_without_finding", "bad_status", "wrong_name",
                     "claims_pass_with_bad_finding", "pass_with_critical", "huge", "huge_file", "nested_fields",
                     "nested_finding", "fat_evidence", "link_response", "hang"):
            with self.subTest(mode=mode):
                self.mode(mode)
                wi, _ = self.weigh()
                self.assertEqual({r["status"] for r in wi["results"]}, {"unverified"}, mode)
                self.assertEqual({e["status"] for e in wi["eligibility"].values()}, {"incomplete"})

    def test_a_missing_plugin_is_loud_and_not_a_pass(self):
        verdict = run_bout(self.bout_dir, os.path.join(self.tmp, "out"), self.events)
        self.assertIn("PLUGIN_MISSING:stub.check", verdict["flags"])
        self.assertEqual(verdict["status"], "INCONCLUSIVE")
        self.assertEqual(verdict["recommended"], [])
        self.assertTrue(all(e["status"] == "incomplete" for e in verdict["eligibility"].values()))

    def test_an_officials_only_event_ends_with_people_not_a_bracket(self):
        self.table()
        self.mode("fail_on_word", word="reached a lot of students")
        out = os.path.join(self.tmp, "out")
        verdict = run_bout(self.bout_dir, out, self.events, judges="sim")     # judges are ignored: no bracket
        self.assertEqual(verdict["status"], "INCONCLUSIVE")
        self.assertIn("NO_BRACKET", verdict["flags"])
        self.assertTrue(any("people decide among the survivors" in r for r in verdict["reasons"]))
        self.assertEqual(verdict["evidence_grade"]["bracket"], "not_run")
        self.assertIn("disqualified", {e["status"] for e in verdict["eligibility"].values()})
        self.assertIn("eligible", {e["status"] for e in verdict["eligibility"].values()})
        with open(os.path.join(out, "REPORT.md"), encoding="utf-8") as fh:
            report = fh.read()
        self.assertIn("Still standing after the checks", report)
        self.assertIn("not a ranking and not a recommendation", report)
        self.assertNotIn("Recommended:", report)
        self.assertTrue(audit(out, verdict["_ledger_head"])["ok"])

    def test_a_plugin_must_be_cleared_for_the_material(self):
        self.table(allowed_sensitivity=["public"])
        with self.assertRaises(Refusal):
            self.weigh()

    def test_a_table_cannot_replace_a_builtin_or_carry_junk(self):
        bad = [{"schema": "barclays.plugins/0.1", "officials": {"text.fact_ledger": {
                    "argv": ["x"], "allowed_sensitivity": ["synthetic"]}}},
               {"schema": "barclays.plugins/0.1", "officials": {"a.b": {"argv": [], "allowed_sensitivity": ["synthetic"]}}},
               {"schema": "barclays.plugins/0.1", "officials": {"a.b": {"argv": ["x"], "allowed_sensitivity": ["secret"]}}},
               {"schema": "barclays.plugins/0.1", "officials": {"a.b": {"argv": ["x"], "allowed_sensitivity": ["synthetic"],
                                                                        "shell": True}}},
               {"schema": "barclays.plugins/0.1", "officials": {"a.b": {"argv": ["python3", "plugins/official.py"],
                                                                        "allowed_sensitivity": ["synthetic"]}}},
               {"schema": "something-else", "officials": {}}]
        for i, doc in enumerate(bad):
            path = os.path.join(self.tmp, f"bad-{i}.json")
            write_json(path, doc)
            with self.subTest(i=i), self.assertRaises(BarclaysError):
                external.load_plugins(path)


if __name__ == "__main__":
    unittest.main()
