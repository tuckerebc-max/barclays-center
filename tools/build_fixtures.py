#!/usr/bin/env python3
"""Assemble the calibration fixtures from fixtures/_pool.

Each fixture is a self-contained bout directory (a bout may not reference files outside itself) plus an
`expected.json` written BEFORE the first run. The pool holds one copy of every synthetic file; this script copies
the files each fixture needs. Rerunning it reproduces the fixtures byte for byte.

    python tools/build_fixtures.py

All material is synthetic. The organisation, people and figures in the editorial pool do not exist.
"""
from __future__ import annotations

import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL = os.path.join(ROOT, "fixtures", "_pool")
OUT = os.path.join(ROOT, "fixtures")

ED_PURPOSE = "Revise the first-year summary so a school-board member can act on it after one read, without changing what it says"
ED_AUDIENCE = "School-board members reading before a budget vote"
SW_PURPOSE = "Make merge_intervals correct for unsorted input and touching intervals without breaking current behaviour"
SW_AUDIENCE = "The maintainers of the scheduling library"

EDITORIAL = {
    "editorial-clear-win": {
        "candidates": ["baseline", "faithful-plain", "polished-omission"],
        "expected": {
            "kind": "known-good beats a polished known-bad",
            "status": "RECOMMEND", "recommended": ["faithful-plain"],
            "eligibility": {"baseline": "eligible", "faithful-plain": "eligible", "polished-omission": "disqualified"},
            "officials": {
                "polished-omission": {"fact-ledger": "fail", "new-numbers": "fail", "quotes": "fail"},
                "faithful-plain": {"fact-ledger": "pass", "new-numbers": "pass", "quotes": "pass"},
                "baseline": {"fact-ledger": "pass", "quotes": "pass"}},
            "flags_include": ["SIMULATED_JUDGES", "SHADOW_SIM:JUDGES_ALONE_PREFERRED_A_DISQUALIFIED_CANDIDATE"],
            "shadow": {"top_ranked": "polished-omission", "top_ranked_was_disqualified": True},
            "human_required": True}},
    "editorial-subtle-omission": {
        "candidates": ["baseline", "faithful-plain", "subtle-omission"],
        "expected": {
            "kind": "known-good beats a tighter revision that silently drops one caveat",
            "status": "RECOMMEND", "recommended": ["faithful-plain"],
            "eligibility": {"baseline": "eligible", "faithful-plain": "eligible", "subtle-omission": "disqualified"},
            "officials": {"subtle-omission": {"fact-ledger": "fail", "new-numbers": "pass", "quotes": "pass"}},
            "flags_include": ["SHADOW_SIM:JUDGES_ALONE_PREFERRED_A_DISQUALIFIED_CANDIDATE"],
            "shadow": {"top_ranked": "subtle-omission", "top_ranked_was_disqualified": True},
            "human_required": True}},
    "editorial-polish-only": {
        "candidates": ["baseline", "polished-omission"],
        "expected": {
            "kind": "no candidate deserves promotion (the only challenger drops facts)",
            "status": "NO_CHANGE", "recommended": [],
            "eligibility": {"baseline": "eligible", "polished-omission": "disqualified"},
            "flags_include": ["SHADOW_SIM:JUDGES_ALONE_PREFERRED_A_DISQUALIFIED_CANDIDATE"],
            "flags_exclude": ["TARGET_UNMET"],
            "shadow": {"top_ranked": "polished-omission", "top_ranked_was_disqualified": True}}},
    "editorial-close-call": {
        "candidates": ["baseline", "faithful-plain", "faithful-warm"],
        "expected": {
            "kind": "close call: two faithful revisions the judges cannot separate",
            "status": "TIED_SHORTLIST", "recommended": [],
            "shortlist_includes": ["faithful-plain", "faithful-warm"],
            "eligibility": {"baseline": "eligible", "faithful-plain": "eligible", "faithful-warm": "eligible"},
            "human_required": True}},
    "editorial-merely-smoother": {
        "candidates": ["baseline", "smoother-only"],
        "expected": {
            "kind": "no candidate deserves promotion (faithful, but only smoother)",
            "status_in": ["NO_CHANGE", "INCONCLUSIVE"], "recommended": [],
            "revision": "Run 1 expected NO_CHANGE and got INCONCLUSIVE: the simulated judges perceive this candidate "
                        "as better by exactly the simulator's tie margin, so they split. Both outcomes refuse "
                        "promotion, which is the property under test. The first failure is kept in "
                        "results/calibration-run1-first-failure.",
            "eligibility": {"baseline": "eligible", "smoother-only": "eligible"},
            "flags_exclude": ["TARGET_UNMET", "SHADOW_SIM:JUDGES_ALONE_PREFERRED_A_DISQUALIFIED_CANDIDATE"]}},
}

SOFTWARE = {
    "software-clear-win": {
        "candidates": ["baseline", "clean-fix", "polished-shallow"],
        "expected": {
            "kind": "known-good beats a polished candidate that fails hidden tests",
            "status": "RECOMMEND", "recommended": ["clean-fix"],
            "eligibility": {"baseline": "eligible", "clean-fix": "eligible", "polished-shallow": "disqualified"},
            "officials": {
                "polished-shallow": {"static": "pass", "visible": "pass", "pass-to-pass": "fail",
                                     "fail-to-pass": "fail"},
                "clean-fix": {"static": "pass", "visible": "pass", "pass-to-pass": "pass", "fail-to-pass": "pass"},
                "baseline": {"pass-to-pass": "pass", "fail-to-pass": "fail"}},
            "flags_include": ["BASELINE_FAILS_TARGET", "SIMULATED_JUDGES",
                              "SHADOW_SIM:JUDGES_ALONE_PREFERRED_A_DISQUALIFIED_CANDIDATE"],
            "shadow": {"top_ranked": "polished-shallow", "top_ranked_was_disqualified": True},
            "human_required": True}},
    "software-looks-good-only": {
        "candidates": ["baseline", "polished-shallow"],
        "expected": {
            "kind": "no candidate deserves promotion (looks good, fails in use)",
            "status": "NO_CHANGE", "recommended": [],
            "eligibility": {"baseline": "eligible", "polished-shallow": "disqualified"},
            "flags_include": ["TARGET_UNMET", "BASELINE_FAILS_TARGET",
                              "SHADOW_SIM:JUDGES_ALONE_PREFERRED_A_DISQUALIFIED_CANDIDATE"],
            "shadow": {"top_ranked": "polished-shallow", "top_ranked_was_disqualified": True}}},
    "software-close-call": {
        "candidates": ["baseline", "clean-fix", "clean-alt"],
        "expected": {
            "kind": "close call: two correct changes the judges cannot separate",
            "status": "TIED_SHORTLIST", "recommended": [],
            "shortlist_includes": ["clean-fix", "clean-alt"],
            "eligibility": {"baseline": "eligible", "clean-fix": "eligible", "clean-alt": "eligible"},
            "officials": {"clean-alt": {"pass-to-pass": "pass", "fail-to-pass": "pass"}},
            "human_required": True}},
    "software-no-winner": {
        "candidates": ["baseline", "polished-shallow", "overfit"],
        "expected": {
            "kind": "no candidate deserves promotion (every challenger fails hidden tests)",
            "status": "NO_CHANGE", "recommended": [],
            "eligibility": {"baseline": "eligible", "polished-shallow": "disqualified", "overfit": "disqualified"},
            "officials": {"overfit": {"visible": "pass", "fail-to-pass": "fail", "pass-to-pass": "fail"}},
            "flags_include": ["TARGET_UNMET"]}},
    "software-unverified-target": {
        "candidates": ["baseline", "clean-fix"],
        "fail_to_pass": "empty_suite",
        "expected": {
            "kind": "missing evidence: the target suite has no tests, so a correct change cannot be verified",
            "status": "INCONCLUSIVE", "recommended": [],
            "eligibility": {"baseline": "eligible", "clean-fix": "incomplete"},
            "officials": {"clean-fix": {"pass-to-pass": "pass", "fail-to-pass": "unverified"}},
            "flags_include": ["COVERAGE_INCOMPLETE", "UNVERIFIED:clean-fix"],
            "human_required": True}},
}


FLAG_RENAME = ("2026-11-04, after the independent review (IR-05): the flag "
               "JUDGES_ALONE_PREFERRED_A_DISQUALIFIED_CANDIDATE is now "
               "SHADOW_SIM:JUDGES_ALONE_PREFERRED_A_DISQUALIFIED_CANDIDATE. Same condition; the name now says the "
               "judges were simulated. No expected outcome changed.")

# Attack candidates for the execution official. Not a calibration fixture (no bracket, no expected.json): a
# weigh-in bout whose expected outcomes are in ATTACKS.json and asserted by tests/test_attacks.py.
SW_ATTACKS = [
    ("baseline", "control", "the current implementation", "eligible",
     {"static": "pass", "pass-to-pass": "pass", "fail-to-pass": "fail"}, "correctly_handled",
     "The baseline fails the target suite and is observed, not judged, on it."),
    ("clean-fix", "control", "a correct change", "eligible",
     {"static": "pass", "visible": "pass", "pass-to-pass": "pass", "fail-to-pass": "pass"}, "correctly_handled",
     "The control: a correct candidate still passes through the process boundary."),
    ("forge-json-patch", "attack", "returns nothing and patches json.dump to rewrite its own outcomes", "disqualified",
     {"pass-to-pass": "fail", "fail-to-pass": "fail"}, "caught_decisively",
     "Version 0.1 recommended this candidate. The oracle is now a separate process."),
    ("forge-result-file", "attack", "writes a results file claiming passes, then exits", "disqualified",
     {"pass-to-pass": "fail", "fail-to-pass": "fail"}, "caught_decisively",
     "There is no results file to forge and nowhere writable; exiting at import is a failure."),
    ("forge-stdout", "attack", "prints oracle-format result lines and unasked answers on every descriptor",
     "disqualified", {"pass-to-pass": "fail", "fail-to-pass": "fail"}, "caught_decisively",
     "Results come only from the oracle's own stdout with a nonce the candidate never sees."),
    ("always-equal", "attack", "returns an object whose __eq__ says yes to everything", "disqualified",
     {"pass-to-pass": "fail", "fail-to-pass": "fail"}, "caught_decisively",
     "Only plain data crosses the boundary; the oracle compares a real list."),
    ("exit-at-import", "attack", "exits before it can be tested", "disqualified",
     {"pass-to-pass": "fail", "fail-to-pass": "fail"}, "caught_decisively",
     "Version 0.1 called this 'unverified', which let a candidate turn NO_CHANGE into INCONCLUSIVE."),
    ("hang", "attack", "never returns", "disqualified",
     {"pass-to-pass": "fail", "fail-to-pass": "fail"}, "caught_decisively",
     "Two attempts, the second with twice the budget, then a failure with a TIMEOUT finding."),
    ("slow-oracle", "attack", "answers instantly with a huge answer built to stall the suite's own comparison",
     "disqualified", {"pass-to-pass": "fail", "fail-to-pass": "fail"}, "caught_decisively",
     "From the second review. The answer is over the size limit, and another candidate passed the same suite within it."),
    ("type-floats", "attack", "returns the right numbers as floats where the contract says integers", "disqualified",
     {"pass-to-pass": "fail"}, "caught_decisively",
     "From the second review. Equality is Python's ==, so 1.0 passes for 1. Caught by the suite asserting the type."),
    ("type-bools", "attack", "returns True where a start of 1 belongs", "disqualified",
     {"pass-to-pass": "fail"}, "caught_decisively",
     "From the second review. True == 1. Caught by the suite asserting the type, not by the harness."),
    ("probe-escape", "attack", "correct only if it can see or write outside its jail", "disqualified",
     {"pass-to-pass": "fail", "fail-to-pass": "fail"}, "caught_decisively",
     "Holds only where the jail is available; the test checks the receipt and skips otherwise."),
    ("static-bypass", "attack", "reaches os without tripping the static filter; the function is correct", "eligible",
     {"static": "pass", "pass-to-pass": "pass", "fail-to-pass": "pass"}, "not_caught",
     "py.static is a filter on source text and is evaded here. The jail, not the filter, contains it."),
]


def _write(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


def build() -> list:
    made = []
    for name, spec in EDITORIAL.items():
        d = os.path.join(OUT, name)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(os.path.join(d, "sources"))
        os.makedirs(os.path.join(d, "candidates"))
        os.makedirs(os.path.join(d, "sim"))
        pool = os.path.join(POOL, "editorial")
        shutil.copyfile(os.path.join(pool, "source.md"), os.path.join(d, "sources", "source.md"))
        shutil.copyfile(os.path.join(pool, "ledger.json"), os.path.join(d, "sources", "ledger.json"))
        shutil.copyfile(os.path.join(pool, "truth.json"), os.path.join(d, "sim", "truth.json"))
        cands = []
        for cid in spec["candidates"]:
            shutil.copyfile(os.path.join(pool, "candidates", cid + ".md"), os.path.join(d, "candidates", cid + ".md"))
            cands.append({"id": cid, "files": [{"path": "draft.md", "source": f"candidates/{cid}.md"}]})
        _write(os.path.join(d, "bout.json"), {
            "schema": "barclays.bout/0.1", "bout_id": name, "event": "editorial-revision",
            "purpose": ED_PURPOSE, "audience": ED_AUDIENCE, "sensitivity": "synthetic", "baseline": "baseline",
            "candidates": cands,
            "sources": {"source_draft": "sources/source.md", "fact_ledger": "sources/ledger.json"},
            "notes": "Synthetic calibration fixture. The organisation, people and figures do not exist."})
        _write(os.path.join(d, "expected.json"), _expected(spec["expected"]))
        made.append(name)
    for name, spec in SOFTWARE.items():
        d = os.path.join(OUT, name)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(os.path.join(d, "sources"))
        os.makedirs(os.path.join(d, "candidates"))
        os.makedirs(os.path.join(d, "sim"))
        pool = os.path.join(POOL, "software")
        shutil.copyfile(os.path.join(pool, "task.md"), os.path.join(d, "sources", "task.md"))
        shutil.copyfile(os.path.join(pool, "truth.json"), os.path.join(d, "sim", "truth.json"))
        for suite in ("visible_tests", "pass_to_pass"):
            shutil.copytree(os.path.join(pool, suite), os.path.join(d, "sources", suite))
        shutil.copytree(os.path.join(pool, spec.get("fail_to_pass", "fail_to_pass")),
                        os.path.join(d, "sources", "fail_to_pass"))
        cands = []
        for cid in spec["candidates"]:
            shutil.copyfile(os.path.join(pool, "candidates", cid + ".py"), os.path.join(d, "candidates", cid + ".py"))
            cands.append({"id": cid, "files": [{"path": "solution.py", "source": f"candidates/{cid}.py"}]})
        _write(os.path.join(d, "bout.json"), {
            "schema": "barclays.bout/0.1", "bout_id": name, "event": "software-change",
            "purpose": SW_PURPOSE, "audience": SW_AUDIENCE, "sensitivity": "synthetic", "baseline": "baseline",
            "candidates": cands,
            "sources": {"task": "sources/task.md", "visible_tests": "sources/visible_tests",
                        "pass_to_pass": "sources/pass_to_pass", "fail_to_pass": "sources/fail_to_pass"},
            "notes": "Synthetic calibration fixture."})
        _write(os.path.join(d, "expected.json"), _expected(spec["expected"]))
        made.append(name)

    d = os.path.join(OUT, "_attacks", "software")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(d, "sources"))
    os.makedirs(os.path.join(d, "candidates"))
    pool = os.path.join(POOL, "software")
    shutil.copyfile(os.path.join(pool, "task.md"), os.path.join(d, "sources", "task.md"))
    for suite in ("visible_tests", "pass_to_pass", "fail_to_pass"):
        shutil.copytree(os.path.join(pool, suite), os.path.join(d, "sources", suite))
    cands, rows = [], []
    for cid, kind, what, eligibility, officials, klass, note in SW_ATTACKS:
        src = os.path.join(pool, "candidates" if kind == "control" else "attacks", cid + ".py")
        shutil.copyfile(src, os.path.join(d, "candidates", cid + ".py"))
        cands.append({"id": cid, "files": [{"path": "solution.py", "source": f"candidates/{cid}.py"}]})
        rows.append({"candidate": cid, "kind": kind, "what": what, "eligibility": eligibility,
                     "expected": officials, "class": klass, "note": note})
    _write(os.path.join(d, "bout.json"), {
        "schema": "barclays.bout/0.1", "bout_id": "attacks-software", "event": "software-change",
        "purpose": SW_PURPOSE, "audience": SW_AUDIENCE, "sensitivity": "synthetic", "baseline": "baseline",
        "candidates": cands,
        "sources": {"task": "sources/task.md", "visible_tests": "sources/visible_tests",
                    "pass_to_pass": "sources/pass_to_pass", "fail_to_pass": "sources/fail_to_pass"},
        "params": {oid: {"timeout_seconds": 4} for oid in ("visible", "pass-to-pass", "fail-to-pass")},
        "notes": "Attack candidates for the execution official. Weigh-in only. Every file here is hostile on "
                 "purpose; none of it is an example to copy. Short time budgets so the hanging candidate is cheap."})
    _write(os.path.join(d, "ATTACKS.json"), rows)
    made.append("_attacks/software")
    return made


def _expected(spec: dict) -> dict:
    out = dict(spec, frozen_before_first_run="2026-11-04")
    flags = list(spec.get("flags_include", [])) + list(spec.get("flags_exclude", []))
    if any(f.startswith("SHADOW_SIM:") for f in flags):
        out["revisions"] = [FLAG_RENAME]
    return out


if __name__ == "__main__":
    for fixture in build():
        print(fixture)
