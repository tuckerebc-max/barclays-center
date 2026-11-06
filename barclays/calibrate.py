"""Calibration: run fixture bouts against expectations frozen before the run, then probe the judging.

Three questions, kept separate:

  1. Do the OFFICIALS discriminate? Each fixture names, per candidate and official, the status it must get
     (known-good must pass, planted defects must fail). This is real execution on synthetic material.
  2. Does the VENUE reach the expected verdict, including 'no clear winner' and 'no change'?
  3. How much does the JUDGING move the result? The same bout is rerun across seeds and with position-biased
     simulated judges, and a shadow bracket shows what the judges alone would have picked.

Simulated judges answer question 3 only about the workflow: they show the venue holds when judges are noisy,
biased or fooled by polish. They say nothing about how real models judge these artifacts.
"""
from __future__ import annotations

import os
import shutil
import subprocess

from .bracket import SIM_MODELS
from .canon import read_json, sha256_file, tree_hash, write_json
from .errors import BarclaysError, Refusal
from .runner import run_bout


def check_frozen(fixtures_dir: str, events_dir: str, fixtures: list) -> dict:
    """Refuse to calibrate against inputs that differ from what was frozen (fixtures/FROZEN.json).

    The whole fixture directory is hashed, not just its expectation, and so is every event card: a changed
    candidate, ledger, simulator truth file or rule is a different experiment and must be frozen again, on purpose.
    """
    path = os.path.join(fixtures_dir, "FROZEN.json")
    if not os.path.isfile(path):
        raise Refusal(f"no {path}: freeze the fixtures and event cards first (python tools/freeze.py), commit, "
                      "then calibrate")
    frozen = read_json(path)
    changed = []
    for name in fixtures:
        if (frozen.get("fixtures", {}).get(name) or {}).get("tree") != tree_hash(os.path.join(fixtures_dir, name)):
            changed.append(f"fixture {name}")
    for name in sorted(os.listdir(events_dir)):
        if name.endswith(".json") and frozen.get("events", {}).get(name) != sha256_file(
                os.path.join(events_dir, name)):
            changed.append(f"event card {name}")
    if changed:
        raise Refusal("these differ from what was frozen: " + ", ".join(changed) + ". A changed fixture or rule "
                      "is a new experiment: review the change, run python tools/freeze.py, commit, then calibrate.")
    info = {"frozen_sha256": sha256_file(path), "git_commit": None, "git_dirty": None}
    try:
        root = os.path.dirname(os.path.abspath(fixtures_dir))
        head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        if head.returncode == 0:
            info["git_commit"] = head.stdout.strip()
            dirty = subprocess.run(["git", "-C", root, "status", "--porcelain", "--", "barclays", "events",
                                    "fixtures", "lenses", "bc.py"], capture_output=True, text=True, timeout=20)
            info["git_dirty"] = bool(dirty.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return info


def _compare(expected: dict, verdict: dict) -> list:
    """Mismatches between a frozen expectation and an actual verdict. Empty means the fixture is met."""
    miss = []
    if "status" in expected and verdict["status"] != expected["status"]:
        miss.append(f"status: expected {expected['status']}, got {verdict['status']}")
    if "status_in" in expected and verdict["status"] not in expected["status_in"]:
        miss.append(f"status: expected one of {expected['status_in']}, got {verdict['status']}")
    if "recommended" in expected and sorted(verdict["recommended"]) != sorted(expected["recommended"]):
        miss.append(f"recommended: expected {expected['recommended']}, got {verdict['recommended']}")
    if "shortlist_includes" in expected:
        lacking = [c for c in expected["shortlist_includes"] if c not in verdict["shortlist"]]
        if lacking:
            miss.append(f"shortlist lacks {lacking} (got {verdict['shortlist']})")
    for cid, want in (expected.get("eligibility") or {}).items():
        got = verdict["eligibility"].get(cid, {}).get("status")
        if got != want:
            miss.append(f"eligibility[{cid}]: expected {want}, got {got}")
    for flag in expected.get("flags_include") or []:
        if flag not in verdict["flags"]:
            miss.append(f"flag {flag} missing")
    for flag in expected.get("flags_exclude") or []:
        if flag in verdict["flags"]:
            miss.append(f"flag {flag} present but should not be")
    results = verdict["_weigh_in"]["results"]
    for cid, per in (expected.get("officials") or {}).items():
        for oid, want in per.items():
            got = next((r["status"] for r in results if r["candidate_id"] == cid and r["official_id"] == oid), None)
            if got != want:
                miss.append(f"official {oid} on {cid}: expected {want}, got {got}")
    sh = expected.get("shadow")
    if sh:
        view = verdict.get("shadow_bracket") or {}
        if "top_ranked" in sh and (view.get("ranking") or [None])[0] != sh["top_ranked"]:
            miss.append(f"shadow top-ranked: expected {sh['top_ranked']}, got {(view.get('ranking') or [None])[0]}")
        if "top_ranked_was_disqualified" in sh and view.get("top_ranked_was_disqualified") != \
                sh["top_ranked_was_disqualified"]:
            miss.append("shadow: top_ranked_was_disqualified is "
                        f"{view.get('top_ranked_was_disqualified')}, expected {sh['top_ranked_was_disqualified']}")
    if "human_required" in expected and verdict["human_decision"]["required"] != expected["human_required"]:
        miss.append(f"human decision required: expected {expected['human_required']}, "
                    f"got {verdict['human_decision']['required']}")
    return miss


def attack_tables(fixtures_dir: str, out_dir: str, events_dir: str) -> list:
    """Run every attack bout under fixtures/_attacks through the weigh-in and compare it with its ATTACKS.json.

    An attack table records, for each hostile or tricky candidate, what the officials are expected to do with it
    and which class that is: caught decisively, raised only as a lead, or not caught. A row that says 'not caught'
    and is reproduced is a known weakness on the record, not a pass.
    """
    out = []
    adir = os.path.join(fixtures_dir, "_attacks")
    for name in sorted(os.listdir(adir)) if os.path.isdir(adir) else []:
        table = os.path.join(adir, name, "ATTACKS.json")
        if not os.path.isfile(table):
            continue
        verdict = run_bout(os.path.join(adir, name), os.path.join(out_dir, "_attacks", name), events_dir,
                           judges="none")
        results = verdict["_weigh_in"]["results"]
        for row in read_json(table):
            cid = row["candidate"]
            got = {oid: next((r["status"] for r in results if r["candidate_id"] == cid and r["official_id"] == oid),
                             None) for oid in row.get("expected", {})}
            lead_ids = [item["id"] for r in results if r["candidate_id"] == cid for item in r["leads"]]
            missing = [p for p in row.get("lead_ids_include", []) if not any(i.startswith(p) for i in lead_ids)]
            eligibility = verdict["eligibility"][cid]["status"]
            jail_needed = cid == "probe-escape" and not any(
                str((r.get("receipt") or {}).get("filesystem", "")).startswith("isolated") for r in results
                if r["candidate_id"] == cid)
            out.append({"bout": name, "candidate": cid, "kind": row.get("kind"), "class": row.get("class"),
                        "what": row.get("what"), "note": row.get("note"),
                        "expected_eligibility": row.get("eligibility"), "eligibility": eligibility,
                        "expected": row.get("expected"), "got": got, "leads": lead_ids,
                        "reproduced": (eligibility == row.get("eligibility") and got == row.get("expected")
                                       and not missing) or jail_needed,
                        "skipped_no_jail": jail_needed})
    return out


def calibrate(fixtures_dir: str, out_dir: str, events_dir: str, atr: str | None, atr_python: str | None,
              seeds=(11, 12, 13, 14, 15), biases=(0.0, 0.25)) -> dict:
    if os.path.exists(out_dir) and os.listdir(out_dir):
        raise BarclaysError(f"calibration output directory is not empty: {out_dir}")
    os.makedirs(out_dir, exist_ok=True)
    fixtures = sorted(d for d in os.listdir(fixtures_dir)
                      if os.path.isfile(os.path.join(fixtures_dir, d, "bout.json"))
                      and os.path.isfile(os.path.join(fixtures_dir, d, "expected.json")))
    if not fixtures:
        raise BarclaysError(f"no fixtures with bout.json and expected.json under {fixtures_dir}")
    frozen = check_frozen(fixtures_dir, events_dir, fixtures)
    rows = []
    for name in fixtures:
        fdir = os.path.join(fixtures_dir, name)
        expected = read_json(os.path.join(fdir, "expected.json"))
        verdict = run_bout(fdir, os.path.join(out_dir, name, "main"), events_dir, judges="sim", atr=atr,
                           atr_python=atr_python, shadow=True)
        misses = _compare(expected, verdict)
        row = {"fixture": name, "event": verdict["event_id"], "kind": expected.get("kind", ""),
               "expected_sha256": sha256_file(os.path.join(fdir, "expected.json")),
               "expected_status": expected.get("status") or " or ".join(expected.get("status_in", [])),
               "status": verdict["status"],
               "recommended": verdict["recommended"], "shortlist": verdict["shortlist"],
               "flags": verdict["flags"], "met": not misses, "mismatches": misses,
               "ledger_head": verdict["_ledger_head"],
               "shadow": verdict.get("shadow_bracket"),
               "bracket_calls": ((verdict.get("bracket") or {}).get("usage") or {}).get("calls_used"),
               "bracket_tokens": ((verdict.get("bracket") or {}).get("usage") or {}).get("tokens_used"),
               "official_ms": sum(r["duration_ms"] for r in verdict["_weigh_in"]["results"]),
               "probes": []}
        if verdict.get("bracket"):
            for bias in biases:
                outcomes = []
                for seed in seeds:
                    pdir = os.path.join(out_dir, name, f"probe-bias{bias}-seed{seed}")
                    behaviors = {alias: {"position_bias": bias} for alias, _ in SIM_MODELS}
                    pv = run_bout(fdir, pdir, events_dir, judges="sim", atr=atr, atr_python=atr_python, seed=seed,
                                  behaviors=behaviors)
                    flips = [d.get("flip_rate", 0.0) for d in
                             ((pv.get("bracket") or {}).get("judge_diagnostics") or {}).values()]
                    outcomes.append({"seed": seed, "status": pv["status"], "recommended": pv["recommended"],
                                     "max_judge_flip_rate": max(flips) if flips else None})
                    shutil.rmtree(os.path.join(pdir, "objects"), ignore_errors=True)  # keep probes small
                same = sum(1 for o in outcomes if o["status"] == verdict["status"]
                           and sorted(o["recommended"]) == sorted(verdict["recommended"]))
                row["probes"].append({"position_bias": bias, "runs": len(outcomes), "same_as_main": same,
                                      "statuses": sorted({o["status"] for o in outcomes}), "outcomes": outcomes})
        rows.append(row)
    summary = {
        "fixtures": len(rows), "met": sum(1 for r in rows if r["met"]),
        "judging": "simulated (controller's sim provider); weigh-in results are real executions on synthetic files",
        "frozen": frozen,
        "seeds": list(seeds), "position_biases": list(biases), "rows": rows,
        "attacks": attack_tables(fixtures_dir, out_dir, events_dir),
    }
    write_json(os.path.join(out_dir, "calibration.json"), summary)
    with open(os.path.join(out_dir, "CALIBRATION-RESULTS.md"), "w", encoding="utf-8") as fh:
        fh.write(render(summary))
    return summary


def render(summary: dict) -> str:
    fz = summary.get("frozen") or {}
    out = ["# Calibration results", "",
           f"{summary['met']} of {summary['fixtures']} fixtures reproduced their frozen expectation.", "",
           "What that sentence covers. The weigh-in is real: the officials ran on the fixture files, and the "
           "planted defects were or were not caught. The verdict path is real plumbing. The judges are SIMULATED, "
           "and each fixture tells the simulator what to perceive (sim/truth.json), so a matching verdict shows "
           "that the venue turns those perceptions into the right decision. It is not evidence about how any "
           "model judges, and it must not be quoted as judge calibration.", "",
           f"Inputs frozen in `fixtures/FROZEN.json` (sha256 `{str(fz.get('frozen_sha256'))[:16]}`), git commit "
           f"`{str(fz.get('git_commit'))[:12]}`, working tree "
           f"{'DIRTY' if fz.get('git_dirty') else 'clean' if fz.get('git_dirty') is False else 'unknown'} for "
           "code, events, fixtures and lenses.", "",
           "| Fixture | Kind | Expected | Got | Recommended / shortlist | Met | Shadow: judges alone ranked first | "
           "Judge calls |", "|---|---|---|---|---|---|---|---|"]
    for r in summary["rows"]:
        sh = r.get("shadow") or {}
        top = (sh.get("ranking") or ["—"])[0]
        note = f"`{top}`" + (" (disqualified at weigh-in)" if sh.get("top_ranked_was_disqualified") else "")
        picks = ", ".join(r["recommended"] or r["shortlist"]) or "—"
        out.append(f"| `{r['fixture']}` | {r['kind']} | {r['expected_status']} | {r['status']} | {picks} | "
                   f"{'yes' if r['met'] else 'NO'} | {note} | {r['bracket_calls'] if r['bracket_calls'] else '—'} |")
    out += ["", "## Stability under reseeding and position-biased judges", "",
            "Each bout that reached a bracket was rerun with new seeds, with and without position bias in every "
            "simulated judge. 'Same' counts runs whose status and recommendation matched the main run.", "",
            "| Fixture | Position bias | Runs | Same as main | Statuses seen |", "|---|---|---|---|---|"]
    for r in summary["rows"]:
        for p in r["probes"]:
            out.append(f"| `{r['fixture']}` | {p['position_bias']} | {p['runs']} | {p['same_as_main']} | "
                       f"{', '.join(p['statuses'])} |")
    bad = [r for r in summary["rows"] if not r["met"]]
    if bad:
        out += ["", "## Mismatches", ""]
        for r in bad:
            out += [f"### `{r['fixture']}`"] + [f"- {m}" for m in r["mismatches"]]
    attacks = summary.get("attacks") or []
    if attacks:
        classes = {}
        for a in attacks:
            classes[a["class"]] = classes.get(a["class"], 0) + 1
        out += ["", "## Attack tables (weigh-in only, real execution)", "",
                f"{sum(1 for a in attacks if a['reproduced'])} of {len(attacks)} rows behaved as recorded in "
                "`fixtures/_attacks/*/ATTACKS.json`. 'As recorded' includes the rows recorded as NOT caught: "
                + ", ".join(f"{n} {c.replace('_', ' ')}" for c, n in sorted(classes.items())) + ".", "",
                "| Bout | Candidate | What it does | Class | Eligibility | As recorded |", "|---|---|---|---|---|---|"]
        for a in attacks:
            out.append(f"| {a['bout']} | `{a['candidate']}` | {str(a['what']).replace('|', '/')} | "
                       f"{str(a['class']).replace('_', ' ')} | {a['eligibility']} | "
                       f"{'yes' if a['reproduced'] and not a['skipped_no_jail'] else 'skipped (no jail on this host)' if a['skipped_no_jail'] else 'NO'} |")
    return "\n".join(out) + "\n"
