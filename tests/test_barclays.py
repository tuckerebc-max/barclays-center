"""Barclays Center tests. Standard library only. Run from the repository root:

    python -B -m unittest discover -s tests -v

Tests that need the tournament controller (adversarial-tournament-review) look for it via BARCLAYS_ATR or a sibling
checkout and are skipped, with the reason, when it is absent.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from barclays import officials  # noqa: E402
from barclays.bracket import find_atr, find_python  # noqa: E402
from barclays.canon import read_json, write_json  # noqa: E402
from barclays.errors import BarclaysError, Refusal  # noqa: E402
from barclays.ledger import Ledger, verify  # noqa: E402
from barclays.lenses import export_panel, import_panel, load_lens, load_lenses  # noqa: E402
from barclays.officials.base import Ctx  # noqa: E402
from barclays.officials.text_fidelity import match_fact, norm, numbers_in  # noqa: E402
from barclays.runner import _load, open_run, run_bout, write_manifest  # noqa: E402
from barclays.spec import check_privacy, load_bout, load_event  # noqa: E402
from barclays.weighin import run_weigh_in  # noqa: E402

EVENTS = os.path.join(ROOT, "events")
LENSES = os.path.join(ROOT, "lenses")
FIX = os.path.join(ROOT, "fixtures")


def have_controller():
    try:
        return find_atr(None), find_python(None)
    except Refusal as exc:
        return None, str(exc)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bc-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def copy_fixture(self, name):
        dst = os.path.join(self.tmp, name)
        shutil.copytree(os.path.join(FIX, name), dst)
        return dst

    def weigh(self, bout_dir):
        bout, event = _load(bout_dir, EVENTS)
        out = os.path.join(self.tmp, "run-" + os.path.basename(bout_dir) + str(len(os.listdir(self.tmp))))
        ledger = open_run(out)
        write_manifest(bout, event, ledger, out)
        return bout, event, run_weigh_in(bout, event, out, ledger), out, ledger

    def status(self, wi, cid, oid):
        return next(r["status"] for r in wi["results"] if r["candidate_id"] == cid and r["official_id"] == oid)


class TextFidelity(Base):
    def test_fact_terms_must_fall_in_one_window(self):
        fact = {"match": {"all": [["4,218"], ["students"]], "window": 40}}
        self.assertTrue(match_fact(norm("We tutored 4,218 students this year."), fact)[0])
        far = "The number 4,218 opens the report. " + "Filler sentence. " * 10 + "Many students attended."
        self.assertFalse(match_fact(norm(far), fact)[0])

    def test_number_inside_a_longer_number_does_not_match(self):
        fact = {"match": {"all": [["4218"]]}}
        self.assertFalse(match_fact(norm("serving 14,218 students"), fact)[0])
        self.assertTrue(match_fact(norm("serving 4,218 students"), fact)[0])

    def test_numbers_normalise_thousands_and_currency(self):
        values = [v for v, _, _ in numbers_in("It cost $2.9 million for 4,218 students, about 40% more; see F2 and v3.")]
        self.assertEqual(values, ["2.9", "4218", "40"])

    def test_polished_candidate_fails_three_officials_and_faithful_passes(self):
        _, _, wi, _, _ = self.weigh(self.copy_fixture("editorial-clear-win"))
        for oid in ("fact-ledger", "new-numbers", "quotes"):
            self.assertEqual(self.status(wi, "polished-omission", oid), "fail", oid)
            self.assertEqual(self.status(wi, "faithful-plain", oid), "pass", oid)
        self.assertEqual(wi["eligibility"]["polished-omission"]["status"], "disqualified")
        self.assertEqual(wi["eligibility"]["faithful-plain"]["status"], "eligible")

    def test_hedge_shift_gives_leads_and_never_fails(self):
        _, _, wi, _, _ = self.weigh(self.copy_fixture("editorial-clear-win"))
        res = next(r for r in wi["results"] if r["candidate_id"] == "polished-omission"
                   and r["official_id"] == "hedge-shift")
        self.assertEqual(res["status"], "pass")
        self.assertTrue(any("proves" in item["note"] for item in res["leads"]))
        clean = next(r for r in wi["results"] if r["candidate_id"] == "faithful-plain"
                     and r["official_id"] == "hedge-shift")
        self.assertEqual(clean["leads"], [])

    def test_broken_ledger_is_unverified_not_a_mass_disqualification(self):
        d = self.copy_fixture("editorial-clear-win")
        ledger = read_json(os.path.join(d, "sources", "ledger.json"))
        ledger["facts"].append({"id": "F99", "statement": "not in the source", "must_keep": True,
                                "match": {"all": [["a phrase the source never uses"]]}})
        write_json(os.path.join(d, "sources", "ledger.json"), ledger)
        _, _, wi, _, _ = self.weigh(d)
        self.assertEqual(self.status(wi, "faithful-plain", "fact-ledger"), "unverified")
        self.assertEqual(wi["eligibility"]["faithful-plain"]["status"], "incomplete")

    def test_quote_with_trailing_comma_is_verbatim(self):
        _, _, wi, _, _ = self.weigh(self.copy_fixture("editorial-close-call"))
        self.assertEqual(self.status(wi, "faithful-warm", "quotes"), "pass")


class Execution(Base):
    def test_hidden_suites_separate_clean_from_polished(self):
        _, _, wi, _, _ = self.weigh(self.copy_fixture("software-clear-win"))
        self.assertEqual(self.status(wi, "polished-shallow", "visible"), "pass")
        self.assertEqual(self.status(wi, "polished-shallow", "pass-to-pass"), "fail")
        self.assertEqual(self.status(wi, "polished-shallow", "fail-to-pass"), "fail")
        for oid in ("visible", "pass-to-pass", "fail-to-pass"):
            self.assertEqual(self.status(wi, "clean-fix", oid), "pass")
        self.assertEqual(wi["eligibility"]["polished-shallow"]["status"], "disqualified")

    def test_baseline_is_observed_not_judged_on_the_target_suite(self):
        _, _, wi, _, _ = self.weigh(self.copy_fixture("software-clear-win"))
        self.assertEqual(self.status(wi, "baseline", "fail-to-pass"), "fail")
        self.assertEqual(wi["eligibility"]["baseline"]["status"], "eligible")
        self.assertTrue(wi["baseline_fails_target"])

    def test_zero_tests_is_unverified_never_a_pass(self):
        _, _, wi, _, _ = self.weigh(self.copy_fixture("software-unverified-target"))
        self.assertEqual(self.status(wi, "clean-fix", "fail-to-pass"), "unverified")
        self.assertEqual(wi["eligibility"]["clean-fix"]["status"], "incomplete")

    def test_a_hanging_candidate_fails_by_timeout(self):
        d = self.copy_fixture("software-clear-win")
        with open(os.path.join(d, "candidates", "clean-fix.py"), "w") as fh:
            fh.write("def merge_intervals(intervals):\n    while True:\n        pass\n")
        bout = read_json(os.path.join(d, "bout.json"))
        bout["params"] = {"pass-to-pass": {"timeout_seconds": 2}, "fail-to-pass": {"timeout_seconds": 2},
                          "visible": {"timeout_seconds": 2}}
        write_json(os.path.join(d, "bout.json"), bout)
        _, _, wi, _, _ = self.weigh(d)
        self.assertEqual(self.status(wi, "clean-fix", "pass-to-pass"), "fail")
        res = next(r for r in wi["results"] if r["candidate_id"] == "clean-fix" and r["official_id"] == "pass-to-pass")
        self.assertTrue(res["receipt"]["timed_out"])

    def test_receipt_records_isolation_honestly(self):
        _, _, wi, _, _ = self.weigh(self.copy_fixture("software-clear-win"))
        res = next(r for r in wi["results"] if r["candidate_id"] == "clean-fix" and r["official_id"] == "pass-to-pass")
        self.assertIn(res["receipt"]["network"], ("denied (network namespace)", "not_enforced"))
        self.assertTrue(res["receipt"]["filesystem"].startswith("isolated")
                        or res["receipt"]["filesystem"] == "not_isolated")
        self.assertTrue(res["receipt"]["result_authenticated"])
        self.assertEqual(len(res["receipt"]["suite_sha256"]), 64)
        self.assertNotIn("stderr_tail", res["receipt"])     # candidate output is recorded by hash and size only

    def test_static_forbids_harness_reach_and_flags_special_casing(self):
        d = self.copy_fixture("software-no-winner")
        _, _, wi, _, _ = self.weigh(d)
        res = next(r for r in wi["results"] if r["candidate_id"] == "overfit" and r["official_id"] == "static")
        self.assertEqual(res["status"], "pass")
        self.assertTrue(any(item["id"] == "SPECIAL-CASING" for item in res["leads"]))
        d2 = self.copy_fixture("software-looks-good-only")
        with open(os.path.join(d2, "candidates", "polished-shallow.py"), "w") as fh:
            fh.write("import os\n\ndef merge_intervals(intervals):\n    return []\n")
        _, _, wi2, _, _ = self.weigh(d2)
        self.assertEqual(self.status(wi2, "polished-shallow", "static"), "fail")

    def test_syntax_error_is_disqualifying(self):
        d = self.copy_fixture("software-looks-good-only")
        with open(os.path.join(d, "candidates", "polished-shallow.py"), "w") as fh:
            fh.write("def merge_intervals(intervals)\n    return []\n")
        _, _, wi, _, _ = self.weigh(d)
        self.assertEqual(self.status(wi, "polished-shallow", "static"), "fail")


class SpecAndPrivacy(Base):
    def test_unknown_keys_and_missing_label_are_rejected(self):
        d = self.copy_fixture("editorial-polish-only")
        bout = read_json(os.path.join(d, "bout.json"))
        bout["sensitivty"] = bout.pop("sensitivity")
        write_json(os.path.join(d, "bout.json"), bout)
        with self.assertRaises(BarclaysError):
            load_bout(d)
        del bout["sensitivty"]
        write_json(os.path.join(d, "bout.json"), bout)
        with self.assertRaises(Refusal):
            load_bout(d)

    def test_paths_may_not_leave_the_bout(self):
        d = self.copy_fixture("editorial-polish-only")
        bout = read_json(os.path.join(d, "bout.json"))
        bout["sources"]["source_draft"] = "../editorial-clear-win/sources/source.md"
        write_json(os.path.join(d, "bout.json"), bout)
        with self.assertRaises(Refusal):
            load_bout(d)

    def test_restricted_material_is_refused_where_code_executes(self):
        d = self.copy_fixture("software-looks-good-only")
        bout = read_json(os.path.join(d, "bout.json"))
        bout["sensitivity"] = "restricted"
        write_json(os.path.join(d, "bout.json"), bout)
        with self.assertRaises(Refusal):
            self.weigh(d)

    def test_privacy_check_fails_closed(self):
        check_privacy("x", ["synthetic"], "synthetic")
        with self.assertRaises(Refusal):
            check_privacy("x", ["synthetic"], "internal")
        with self.assertRaises(Refusal):
            check_privacy("x", [], "synthetic")

    def test_runs_are_append_only(self):
        d = self.copy_fixture("editorial-polish-only")
        out = os.path.join(self.tmp, "run")
        os.makedirs(out)
        open(os.path.join(out, "something"), "w").close()
        with self.assertRaises(Refusal):
            run_bout(d, out, EVENTS, judges="none")

    def test_every_event_card_loads_and_weights_sum_to_one(self):
        for name in os.listdir(EVENTS):
            if name.endswith(".json"):
                card = load_event(os.path.join(EVENTS, name))
                if card["status"] == "runnable":
                    self.assertAlmostEqual(sum(c["weight"] for c in card["criteria"]), 1.0)


class LensesAndPanel(Base):
    def test_a_style_lens_cannot_claim_factual_authority(self):
        card = read_json(os.path.join(LENSES, "plain-language-editor.json"))
        card["may_assess"].append("accuracy")
        path = os.path.join(self.tmp, "bad.json")
        write_json(path, card)
        with self.assertRaises(BarclaysError):
            load_lens(path)

    def _export(self, leads="none"):
        d = self.copy_fixture("editorial-clear-win")
        bout, event, wi, out, ledger = self.weigh(d)
        lenses = load_lenses(LENSES)
        ids = export_panel(out, bout, event, wi, lenses, [("faithful-plain", "polished-omission")], ["r1"], leads,
                           ["synthetic"], ledger)
        return bout, lenses, out, ledger, ids

    def test_packets_are_blind_and_fenced(self):
        bout, _, out, _, ids = self._export("tools")
        self.assertEqual(len(ids), 3 * 2)
        for pid in ids:
            with open(os.path.join(out, "panel", "packets", pid + ".md"), encoding="utf-8") as fh:
                text = fh.read()
            # No candidate ids or file names reach the reviewer, in the packet or in its own file name.
            for leak in ("faithful-plain", "polished-omission", "draft.md", "candidates/"):
                self.assertNotIn(leak, text)
            self.assertRegex(pid, r"^p-[0-9a-f]{12}$")      # random hex: no lens, pair, order or mode in the name
            self.assertIn("<<<DATA-", text)
            self.assertIn("Objective findings", text)
            self.assertIn("Leads (heuristic", text)

    def _pid(self, out, lens_id, order):
        """The opaque packet id for a lens and display order, read from the meta directory reviewers never see."""
        mdir = os.path.join(out, "panel", "meta")
        for name in os.listdir(mdir):
            meta = read_json(os.path.join(mdir, name))
            if meta["lens_id"] == lens_id and meta["order"] == order:
                return meta["packet_id"]
        raise AssertionError(f"no packet for {lens_id} {order}")

    def test_reviewers_not_cleared_for_the_material_get_nothing(self):
        d = self.copy_fixture("editorial-clear-win")
        bout, event, wi, out, ledger = self.weigh(d)
        bout["sensitivity"] = "internal"
        with self.assertRaises(Refusal):
            export_panel(out, bout, event, wi, load_lenses(LENSES), [("faithful-plain", "polished-omission")],
                         ["r1"], "none", ["synthetic", "public"], ledger)
        self.assertFalse(os.path.isdir(os.path.join(out, "panel", "packets")))

    def test_lens_authority_orders_and_locators(self):
        bout, lenses, out, ledger, ids = self._export("none")
        rdir = os.path.join(out, "panel", "results")
        style_ab = self._pid(out, "plain-language-editor", "ab")
        style_ba = self._pid(out, "plain-language-editor", "ba")
        # ab: A = faithful-plain. The style reviewer prefers the polished text in both orders (consistent).
        write_json(os.path.join(rdir, style_ab + ".json"), {
            "preference": "B", "margin": 4, "reasons": "B reads better",
            "objections": [
                {"candidate": "A", "category": "voice", "quote": "The short version", "claim": "flat", "severity": "minor"},
                {"candidate": "A", "category": "accuracy", "quote": "4,218 students", "claim": "figure looks wrong",
                 "severity": "critical"},
                {"candidate": "A", "category": "inference", "quote": "approximately $688", "claim": "risky",
                 "severity": "major"},
                {"candidate": "A", "category": "veracity", "quote": "37 schools", "claim": "this is false",
                 "severity": "critical"},
                {"candidate": "B", "category": "clarity", "quote": "this passage is not in the text", "claim": "x",
                 "severity": "minor"}],
            "allegations": []})
        write_json(os.path.join(rdir, style_ba + ".json"), {
            "preference": "A", "margin": 2, "reasons": "", "objections": [], "allegations": []})
        # The fact desk flips with display order: order-sensitive, so it abstains.
        for order in ("ab", "ba"):
            write_json(os.path.join(rdir, self._pid(out, "fact-desk", order) + ".json"), {
                "preference": "A", "margin": 3, "reasons": "", "objections": [],
                "allegations": [{"candidate": "B", "quote": "nearly 5,000 students", "claim": "not in the reference"}]
                if order == "ba" else []})
        panel = import_panel(out, bout, lenses, ledger, {"r1": {"model": "test", "real": False}})
        by_lens = {e["lens_id"]: e for e in panel["reconciled"]}
        self.assertEqual(by_lens["plain-language-editor"]["outcome"], "consistent")
        self.assertEqual(by_lens["plain-language-editor"]["preferred"], "polished-omission")
        self.assertEqual(by_lens["fact-desk"]["outcome"], "order_sensitive")
        self.assertEqual(by_lens["fact-desk"]["preferred"], "abstain")
        self.assertEqual(by_lens["measurement-scientist"]["outcome"], "incomplete")
        # A factual objection from a style lens becomes an unverified allegation raised out of lane. So does one
        # filed under a word the venue does not know ("veracity"): an unknown category is not a way round the rule.
        style_alleg = [a for a in panel["allegations"] if a["lens_id"] == "plain-language-editor"]
        self.assertEqual(sorted(a["category"] for a in style_alleg), ["accuracy", "veracity"])
        self.assertTrue(all(a["status"] == "unverified" and not a["raised_in_lane"] for a in style_alleg))
        self.assertFalse(next(a for a in style_alleg if a["category"] == "veracity")["category_recognised"])
        # "inference" is another lens's lane (the measurement scientist's): read, not counted, not an allegation.
        self.assertEqual([o["category"] for o in panel["objections_out_of_lane"]], ["inference"])
        unresolved = [o for o in panel["objections_in_lane"] if not o["locator_resolved"]]
        self.assertEqual(len(unresolved), 1)
        self.assertIn("advisory", panel["authority"])
        ok, problems, _, _ = verify(out)
        self.assertTrue(ok, problems)


class LedgerTests(Base):
    def test_tampering_is_detected(self):
        _, _, _, out, _ = self.weigh(self.copy_fixture("editorial-polish-only"))
        self.assertTrue(verify(out)[0])
        objects = os.path.join(out, "objects")
        victim = os.path.join(objects, sorted(os.listdir(objects))[0])
        with open(victim, "ab") as fh:
            fh.write(b" ")
        ok, problems, _, _ = verify(out)
        self.assertFalse(ok)
        self.assertTrue(any("altered" in p for p in problems))

    def test_removing_an_event_breaks_the_chain(self):
        _, _, _, out, _ = self.weigh(self.copy_fixture("editorial-polish-only"))
        path = os.path.join(out, "ledger.jsonl")
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines[:2] + lines[3:]) + "\n")
        ok, problems, _, _ = verify(out)
        self.assertFalse(ok)
        with self.assertRaises(BarclaysError):
            Ledger(out)


class EndToEnd(Base):
    def setUp(self):
        super().setUp()
        atr, why = have_controller()
        if atr is None:
            self.skipTest("tournament controller not available: " + why)

    def run_fixture(self, name, **kw):
        return run_bout(self.copy_fixture(name), os.path.join(self.tmp, "out-" + name), EVENTS, judges="sim", **kw)

    def test_polish_cannot_hide_an_omission(self):
        v = self.run_fixture("editorial-clear-win", shadow=True)
        self.assertEqual(v["status"], "RECOMMEND")
        self.assertEqual(v["recommended"], ["faithful-plain"])
        self.assertTrue(v["shadow_bracket"]["top_ranked_was_disqualified"])
        self.assertIn("SHADOW_SIM:JUDGES_ALONE_PREFERRED_A_DISQUALIFIED_CANDIDATE", v["flags"])
        self.assertIn("SIMULATED_JUDGES", v["flags"])
        self.assertTrue(v["human_decision"]["required"])
        self.assertEqual(v["acceptance_state"], "pending_owner")
        self.assertTrue(verify(os.path.join(self.tmp, "out-editorial-clear-win"))[0])

    def test_looking_good_is_not_passing(self):
        v = self.run_fixture("software-looks-good-only", shadow=True)
        self.assertEqual(v["status"], "NO_CHANGE")
        self.assertIn("TARGET_UNMET", v["flags"])
        self.assertEqual(v["shadow_bracket"]["recommended"], ["polished-shallow"])
        self.assertIsNone(v["bracket"])

    def test_close_call_is_a_shortlist_not_a_winner(self):
        v = self.run_fixture("software-close-call")
        self.assertEqual(v["status"], "TIED_SHORTLIST")
        self.assertEqual(sorted(v["shortlist"]), ["clean-alt", "clean-fix"])
        self.assertEqual(v["recommended"], [])

    def test_missing_evidence_is_inconclusive_not_a_loss(self):
        v = self.run_fixture("software-unverified-target")
        self.assertEqual(v["status"], "INCONCLUSIVE")
        self.assertIn("UNVERIFIED:clean-fix", v["flags"])

    def test_simulated_judges_need_declared_perceptions(self):
        d = self.copy_fixture("editorial-clear-win")
        shutil.rmtree(os.path.join(d, "sim"))
        with self.assertRaises(Refusal):
            run_bout(d, os.path.join(self.tmp, "o"), EVENTS, judges="sim")


if __name__ == "__main__":
    unittest.main()
