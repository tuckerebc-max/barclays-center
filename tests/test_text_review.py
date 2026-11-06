"""Tests for the text officials' review fixes: all files read, number and spelling folds, quotations, polarity and
number-order leads, and the honest attack bout. Standard library only; run from the repository root."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from barclays import officials  # noqa: E402
from barclays.officials.base import Ctx  # noqa: E402
from barclays.officials.text_fidelity import canonical_numbers, match_fact, norm, quotations  # noqa: E402
from test_barclays import Base, FIX  # noqa: E402

ATTACKS = os.path.join(FIX, "_attacks", "editorial")


def _load_json(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return json.load(fh)


def _vals(text):
    return [v for v, _, _ in canonical_numbers(text)]


class AllText(Base):
    def test_all_text_joins_every_file_and_primary_text_still_works(self):
        a, b = os.path.join(self.tmp, "a.md"), os.path.join(self.tmp, "b.md")
        with open(a, "wb") as fh:
            fh.write(b"first file")
        with open(b, "wb") as fh:
            fh.write(b"second \xff file")
        ctx = Ctx(bout={}, event={}, cfg={"id": "x", "authority": "advise"}, is_baseline=False, workdir=self.tmp,
                  candidate={"id": "c", "files": [{"abs": a}, {"abs": b}]})
        self.assertEqual(ctx.primary_text(), "first file")
        self.assertEqual(ctx.all_text(), "first file\n\nsecond � file")

    def test_a_claim_hidden_in_a_second_file_is_caught(self):
        _, _, wi, _, _ = self.weigh(ATTACKS)
        self.assertEqual(wi["eligibility"]["a-second-file"]["status"], "disqualified")
        self.assertEqual(self.status(wi, "a-second-file", "new-numbers"), "fail")
        self.assertEqual(self.status(wi, "a-second-file", "quotes"), "fail")


class NumberFold(Base):
    def test_equivalent_spellings_are_one_number(self):
        self.assertEqual(_vals("thirty-seven schools"), _vals("37 schools"))
        self.assertEqual(_vals("$2,900,000"), ["2900000"])
        self.assertEqual(_vals("2.9 million"), ["2900000"])
        self.assertEqual(_vals("$2.9 million and $2.9M"), ["2900000", "2900000"])
        for form in ("4,218", "4 218", "4 218", "4 218"):
            self.assertEqual(_vals(f"{form} students"), ["4218"], form)
        self.assertEqual(_vals("two hundred and fifty-three thousand"), ["253000"])
        self.assertEqual(_vals("five thousand dollars"), ["5000"])
        # A percentage is its own kind of figure: 38 percent is "38%", which is not the count 38 (second review).
        self.assertEqual(_vals("thirty-eight percent"), ["38%"])
        self.assertEqual(_vals("38%"), ["38%"])
        self.assertEqual(_vals("the 37th percentile"), ["37th"])

    def test_bare_one_and_a_are_not_numbers_and_percent_stays_percent(self):
        self.assertEqual(_vals("no one knows a thing; one by one"), [])
        self.assertEqual(norm("one student"), "one student")
        self.assertIn("percent", norm("thirty-eight percent"))
        self.assertEqual(_vals("2026 150 students"), ["2026", "150"])

    def test_fact_matching_uses_the_same_fold(self):
        cases = [({"match": {"all": [["37"], ["schools"]]}}, "at thirty-seven schools"),
                 ({"match": {"all": [["2.9 million", "2.9m"]]}}, "cost $2,900,000 in all"),
                 ({"match": {"all": [["4,218", "4218"], ["students"]]}}, "4 218 students")]
        for fact, text in cases:
            self.assertTrue(match_fact(norm(text), fact)[0], text)
        self.assertFalse(match_fact(norm("serving 14 218 students"), {"match": {"all": [["4218"]]}})[0])


class SpellingFold(Base):
    def test_british_and_american_spellings_match(self):
        pairs = [("randomised", "randomized"), ("organisation", "organization"), ("behaviour", "behavior"),
                 ("colour", "color"), ("recognise", "recognize"), ("labour", "labor"),
                 ("neighbours", "neighbors")]
        for uk, us in pairs:
            self.assertEqual(norm(uk), norm(us), uk)
        fact = {"match": {"all": [["not randomized"]]}}
        self.assertTrue(match_fact(norm("it was not randomised"), fact)[0])
        self.assertNotEqual(norm("hour"), norm("hor"))
        self.assertNotEqual(norm("prise"), norm("prize"))


class Quotations(Base):
    def test_quotation_marks_of_every_kind_are_found(self):
        text = ("He said “curly double words here” and ‘curly single words here’ and "
                "'straight single words here' and \"line one of\nthe quote\" but don't count the evaluator's "
                "apostrophes or the students' work.").translate(
            str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"}))
        found = [q for _, q in quotations(text)]
        self.assertEqual(found, ["curly double words here", "curly single words here", "straight single words here",
                                 "line one of\nthe quote"])

    def test_fabricated_short_and_single_quoted_quotations_fail(self):
        _, _, wi, _, _ = self.weigh(ATTACKS)
        res = next(r for r in wi["results"] if r["candidate_id"] == "a-quotes" and r["official_id"] == "quotes")
        self.assertEqual(res["status"], "fail")
        self.assertEqual(len(res["findings"]), 2)
        self.assertEqual(self.status(wi, "a-footnote", "quotes"), "fail")  # runs across a line break

    def test_ellipsis_splits_the_quotation_into_ordered_segments(self):
        _, _, wi, _, _ = self.weigh(ATTACKS)
        self.assertEqual(self.status(wi, "fp-ellipsis", "quotes"), "pass")
        from barclays.officials.text_fidelity import _in_order
        ref = norm('"the results are encouraging but do not yet show that tutoring caused the gains."')
        self.assertTrue(_in_order(ref, ["the results are encouraging but", "do not yet show"]))
        self.assertFalse(_in_order(ref, ["do not yet show", "the results are encouraging but"]))

    def test_min_words_defaults_to_three_and_stays_a_param(self):
        card = _load_json(ROOT, "events", "editorial-revision.json")
        quotes = next(o for o in card["officials"] if o["id"] == "quotes")
        self.assertEqual(quotes["params"]["min_words"], 3)


class HedgeShiftPolarity(Base):
    def test_every_window_is_checked_and_a_negation_added_is_a_major_lead(self):
        _, _, wi, _, _ = self.weigh(ATTACKS)
        res = next(r for r in wi["results"] if r["candidate_id"] == "a-negate" and r["official_id"] == "hedge-shift")
        self.assertEqual(res["status"], "pass")
        ids = {item["id"]: item for item in res["leads"]}
        for lid in ("P-F1", "P-F2"):
            self.assertEqual(ids[lid]["severity"], "major")
            self.assertIn("polarity", ids[lid]["note"])
            self.assertIn("did not tutor", ids[lid]["note"])
        clean = next(r for r in wi["results"] if r["candidate_id"] == "faithful-plain"
                     and r["official_id"] == "hedge-shift")
        self.assertEqual(clean["leads"], [])

    def test_a_window_past_the_first_is_checked_too(self):
        _, _, wi, _, _ = self.weigh(ATTACKS)
        res = next(r for r in wi["results"] if r["candidate_id"] == "a-second-file"
                   and r["official_id"] == "hedge-shift")
        self.assertTrue(any(item["id"] == "P-F1.2" for item in res["leads"]))  # a window past the first one


class NumberRoles(Base):
    def test_swapped_numbers_raise_a_lead_and_the_faithful_text_does_not(self):
        _, _, wi, _, _ = self.weigh(ATTACKS)
        swap = next(r for r in wi["results"] if r["candidate_id"] == "a-swap" and r["official_id"] == "number-roles")
        self.assertEqual(swap["status"], "pass")
        self.assertEqual(swap["findings"], [])
        self.assertEqual([item["id"] for item in swap["leads"]], ["R-11-8"])
        self.assertIn("opposite order", swap["leads"][0]["note"])
        for cid in ("faithful-plain", "baseline", "fp-dollars", "fp-spelled37", "fp-space-thousands"):
            res = next(r for r in wi["results"] if r["candidate_id"] == cid and r["official_id"] == "number-roles")
            self.assertEqual(res["leads"], [], cid)

    def test_registered_and_cleared_like_the_other_text_officials(self):
        self.assertIn("text.number_roles", officials.REGISTRY)
        self.assertEqual(officials.CLEARANCE["text.number_roles"], officials.CLEARANCE["text.hedge_shift"])
        card = _load_json(ROOT, "events", "editorial-revision.json")
        cfg = next(o for o in card["officials"] if o["id"] == "number-roles")
        self.assertEqual((cfg["authority"], cfg["applies_to"]), ("advise", "all"))


class AttackBout(Base):
    def test_every_row_of_attacks_json_holds_exactly(self):
        rows = _load_json(ATTACKS, "ATTACKS.json")
        _, _, wi, _, _ = self.weigh(ATTACKS)
        bout_ids = [c["id"] for c in _load_json(ATTACKS, "bout.json")["candidates"]]
        self.assertEqual(sorted(r["candidate"] for r in rows), sorted(bout_ids))
        decisive = {"fact-ledger", "new-numbers", "quotes"}
        for row in rows:
            cid = row["candidate"]
            with self.subTest(cid):
                self.assertIn(row["class"], ("caught_decisively", "lead_only", "not_caught", "correctly_passed",
                                             "false_positive_remaining"))
                self.assertEqual(wi["eligibility"][cid]["status"], row["eligibility"])
                for oid, status in row["expected"].items():
                    self.assertEqual(self.status(wi, cid, oid), status, oid)
                for oid in decisive - set(row["expected"]):
                    self.assertEqual(self.status(wi, cid, oid), "pass", oid)
                lead_ids = [item["id"] for r in wi["results"] if r["candidate_id"] == cid for item in r["leads"]]
                for prefix in row.get("lead_ids_include", []):
                    self.assertTrue(any(i == prefix or i.startswith(prefix + ".") for i in lead_ids), prefix)
                if row["class"] == "caught_decisively":
                    self.assertEqual(row["eligibility"], "disqualified")
                if row["class"] in ("lead_only", "not_caught", "correctly_passed"):
                    self.assertEqual(row["eligibility"], "eligible")
                if row["class"] == "lead_only":
                    self.assertTrue(row.get("lead_ids_include"))
                if row["class"] == "false_positive_remaining":
                    self.assertEqual((row["kind"], row["eligibility"]), ("faithful", "disqualified"))

    def test_the_attack_ledger_is_the_pool_ledger(self):
        with open(os.path.join(ATTACKS, "sources", "ledger.json"), "rb") as a, \
                open(os.path.join(FIX, "_pool", "editorial", "ledger.json"), "rb") as b:
            self.assertEqual(a.read(), b.read())
        self.assertFalse(os.path.exists(os.path.join(ATTACKS, "sim")))


if __name__ == "__main__":
    unittest.main()
