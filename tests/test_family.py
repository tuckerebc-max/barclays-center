"""The family: sibling repositories working through the venue (docs/FAMILY.md).

These tests need the siblings checked out beside this repository (or under BARCLAYS_FAMILY_DIR). Each class skips
with a message when its sibling is absent, so the venue's own suite never depends on them. They run the real
plug-ins: a browser for the web and game officials, ruff and bandit for the code officials when installed.

    python -B -m unittest tests.test_family -v
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from barclays.canon import read_json, write_json  # noqa: E402
from barclays.ledger import audit  # noqa: E402
from barclays.lenses import FACT_LANES, OPINION_LANES, export_panel, import_panel, load_lenses  # noqa: E402
from barclays.runner import _load, open_run, run_bout, write_manifest  # noqa: E402
from barclays.weighin import run_weigh_in  # noqa: E402
import plugins_table  # noqa: E402

FAMILY = os.environ.get("BARCLAYS_FAMILY_DIR") or os.path.dirname(ROOT)
EVENTS = os.path.join(ROOT, "events")
LENSES = os.path.join(ROOT, "lenses")
FIX = os.path.join(ROOT, "fixtures")


def sibling(name, *inside):
    path = os.path.join(FAMILY, name, *inside)
    return path if os.path.exists(path) else None


class Family(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bc-family-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(os.environ.pop, "BARCLAYS_PLUGINS", None)
        os.environ.pop("BARCLAYS_PLUGINS", None)

    def install(self):
        built = plugins_table.build(FAMILY)
        path = os.path.join(self.tmp, "plugins.json")
        write_json(path, built["table"])
        os.environ["BARCLAYS_PLUGINS"] = path
        return built

    def weigh(self, bout_dir):
        bout, event = _load(bout_dir, EVENTS)
        out = os.path.join(self.tmp, f"run-{len(os.listdir(self.tmp))}")
        ledger = open_run(out)
        write_manifest(bout, event, ledger, out)
        return bout, event, run_weigh_in(bout, event, out, ledger), out, ledger

    @staticmethod
    def by(wi, cid, oid):
        return next(r for r in wi["results"] if r["candidate_id"] == cid and r["official_id"] == oid)


@unittest.skipUnless(sibling("barclays-officials-code", "official.py"), "barclays-officials-code is not beside the venue")
class CodeOfficials(Family):
    def test_static_checks_advise_and_change_no_eligibility(self):
        self.install()
        d = os.path.join(self.tmp, "bout")
        shutil.copytree(os.path.join(FIX, "software-clear-win"), d)
        expected = read_json(os.path.join(d, "expected.json"))
        _, _, wi, _, _ = self.weigh(d)
        self.assertEqual({c: e["status"] for c, e in wi["eligibility"].items()}, expected["eligibility"])
        for oid in ("secrets", "lint", "security", "complexity"):
            res = self.by(wi, "clean-fix", oid)
            self.assertEqual(res["authority"], "advise")
            self.assertFalse(res["receipt"].get("plugin_missing"), oid)
            self.assertEqual(res["receipt"]["repo"], "barclays-officials-code")
            self.assertIn(res["status"], ("pass", "fail", "unverified"))   # unverified when ruff or bandit is absent

    def test_without_the_plugin_the_same_bout_says_so_and_decides_the_same(self):
        d = os.path.join(self.tmp, "bout")
        shutil.copytree(os.path.join(FIX, "software-clear-win"), d)
        expected = read_json(os.path.join(d, "expected.json"))
        verdict = run_bout(d, os.path.join(self.tmp, "out"), EVENTS, judges="none")
        self.assertEqual({c: e["status"] for c, e in verdict["eligibility"].items()}, expected["eligibility"])
        self.assertIn("PLUGIN_MISSING:code.lint", verdict["flags"])


@unittest.skipUnless(sibling("barclays-officials-web", "fixtures", "bouts", "ui-website-clear-win", "bout.json"),
                     "barclays-officials-web (with its bout fixture) is not beside the venue")
class WebOfficials(Family):
    def test_a_site_that_looks_good_and_is_broken_is_out_before_anyone_judges_it(self):
        self.install()
        d = os.path.join(self.tmp, "bout")
        shutil.copytree(sibling("barclays-officials-web", "fixtures", "bouts", "ui-website-clear-win"), d)
        out = os.path.join(self.tmp, "out")
        verdict = run_bout(d, out, EVENTS)
        elig = {c: e["status"] for c, e in verdict["eligibility"].items()}
        self.assertEqual(elig["polished-but-broken"], "disqualified")
        self.assertIn(elig["clean"], ("eligible", "incomplete"))          # incomplete when axe-core is not installed
        # Fourth review: a page that is clean at load and breaks on the first click used to pass.
        if "interaction-gated" in elig:
            self.assertEqual(elig["interaction-gated"], "disqualified")
        # No model bracket for this event: the checks say who is out, people decide among the rest.
        self.assertEqual(verdict["status"], "INCONCLUSIVE")
        self.assertIn("NO_BRACKET", verdict["flags"])
        self.assertEqual(verdict["recommended"], [])
        self.assertTrue(verdict["human_decision"]["required"])
        self.assertTrue(any("always" in b for b in verdict["human_decision"]["because"]))
        self.assertTrue(audit(out, verdict["_ledger_head"])["ok"])


@unittest.skipUnless(sibling("barclays-officials-game", "fixtures", "bouts", "game-build-clear-win", "bout.json"),
                     "barclays-officials-game (with its bout fixture) is not beside the venue")
class GameOfficials(Family):
    def test_a_game_that_can_seal_the_player_in_is_out_and_nothing_says_the_other_is_fun(self):
        self.install()
        d = os.path.join(self.tmp, "bout")
        shutil.copytree(sibling("barclays-officials-game", "fixtures", "bouts", "game-build-clear-win"), d)
        verdict = run_bout(d, os.path.join(self.tmp, "out"), EVENTS)
        elig = {c: e["status"] for c, e in verdict["eligibility"].items()}
        self.assertEqual(elig["softlock"], "disqualified")
        self.assertEqual(elig["fair"], "eligible")
        # Fourth review: an unwinnable maze whose hook reports a win, and a frozen game hidden under a counter,
        # both passed. With the organiser's referee and situation in the bout's bot script they are out.
        for cid in ("lying-win", "frozen-counter"):
            if cid in elig:
                self.assertEqual(elig[cid], "disqualified", cid)
        self.assertEqual(verdict["status"], "INCONCLUSIVE")
        self.assertEqual(verdict["recommended"], [])
        self.assertTrue(verdict["human_decision"]["required"])
        boundary = " ".join(verdict["human_decision"]["boundary"]).lower()
        self.assertIn("play", boundary)                                   # the card says what only people can show


@unittest.skipUnless(sibling("barclays-lenses", "cards"), "barclays-lenses is not beside the venue")
class LensRegistry(Family):
    def test_registry_cards_load_beside_the_venues_and_claim_no_factual_authority(self):
        cards = load_lenses([LENSES, sibling("barclays-lenses", "cards")])
        registry = [c for c in cards.values() if c["_path"].startswith(sibling("barclays-lenses", "cards"))]
        self.assertGreaterEqual(len(registry), 10)
        for card in registry:
            lanes = set(card["may_assess"])
            self.assertTrue(lanes <= (FACT_LANES if card["kind"] == "fact_desk" else OPINION_LANES), card["lens_id"])

    def test_an_organiser_seats_real_voices_on_a_bouts_panel(self):
        cards = load_lenses([LENSES, sibling("barclays-lenses", "cards")])
        d = os.path.join(self.tmp, "bout")
        shutil.copytree(os.path.join(FIX, "editorial-clear-win"), d)
        bout, event, wi, prun, ledger = self.weigh(d)
        seats = ["prose-craft-skill", "technical-editing", "fact-checker"]
        ids = export_panel(prun, bout, event, wi, cards, [("faithful-plain", "polished-omission")], ["r1"], "tools",
                           ["synthetic"], ledger, lens_ids=seats)
        self.assertEqual(len(ids), 6)                                     # three lenses, one pair, both orders
        roster = read_json(os.path.join(prun, "panel", "roster.json"))
        self.assertEqual(roster["lens_ids"], seats)
        self.assertTrue(roster["fact_desk_present"])
        # A packet shows the lens's brief and never where the card came from or which candidate is which.
        with open(os.path.join(prun, "panel", "packets", ids[0] + ".md"), encoding="utf-8") as fh:
            packet = fh.read()
        self.assertNotIn("sha256=", packet)
        self.assertNotIn("faithful-plain", packet)
        for name in os.listdir(os.path.join(prun, "panel", "meta")):
            meta = read_json(os.path.join(prun, "panel", "meta", name))
            faithful = "A" if meta["labels"]["A"] == "faithful-plain" else "B"
            write_json(os.path.join(prun, "panel", "results", name),
                       {"preference": faithful, "margin": 2, "reasons": "scripted", "objections": [],
                        "allegations": []})
        import_panel(prun, bout, cards, ledger, {"r1": {"model": "scripted test reviewer", "real": False}})
        verdict = run_bout(d, os.path.join(self.tmp, "out"), EVENTS, judges="none", panel_from=prun)
        self.assertIn("PANEL_LENSES_CHOSEN_BY_ORGANISER", verdict["flags"])
        self.assertNotIn("PANEL_NO_FACT_DESK", verdict["flags"])
        self.assertEqual(verdict["panel"]["roster"]["lens_ids"], seats)


class PanelSeats(Family):
    """Needs no sibling: the organiser's choice of lenses with the venue's own cards."""

    def test_a_panel_with_no_fact_desk_is_flagged(self):
        cards = load_lenses(LENSES)
        d = os.path.join(self.tmp, "bout")
        shutil.copytree(os.path.join(FIX, "editorial-clear-win"), d)
        bout, event, wi, prun, ledger = self.weigh(d)
        export_panel(prun, bout, event, wi, cards, [("faithful-plain", "polished-omission")], ["r1"], "none",
                     ["synthetic"], ledger, lens_ids=["plain-language-editor"])
        import_panel(prun, bout, cards, ledger, None)
        verdict = run_bout(d, os.path.join(self.tmp, "out"), EVENTS, judges="none", panel_from=prun)
        self.assertIn("PANEL_NO_FACT_DESK", verdict["flags"])
        self.assertIn("PANEL_LENSES_CHOSEN_BY_ORGANISER", verdict["flags"])

    def test_one_card_may_not_shadow_another(self):
        from barclays.errors import BarclaysError
        twice = os.path.join(self.tmp, "twice")
        os.makedirs(twice)
        shutil.copy(os.path.join(LENSES, "fact-desk.json"), twice)
        with self.assertRaises(BarclaysError):
            load_lenses([LENSES, twice])
        with self.assertRaises(BarclaysError):
            load_lenses(LENSES + os.pathsep + twice)


if __name__ == "__main__":
    unittest.main()
