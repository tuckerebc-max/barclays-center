"""The weigh-in: every official runs on every candidate before any judge sees one.

Eligibility is decided here and nowhere else:

  disqualified   a decisive official failed. Decisive means authority 'disqualify' and the official applies to this
                 candidate (officials marked applies_to 'challengers' observe the baseline but do not decide it).
  incomplete     a decisive official could not establish its property ('unverified'). Missing evidence is not a
                 failure and not a pass; an incomplete candidate cannot be promoted and is not called a loser.
  eligible       every decisive official passed.

Leads and advisory findings never change eligibility. They travel to reviewers, marked as tool output.
"""
from __future__ import annotations

import os
import tempfile
import traceback

from . import officials
from .canon import sha256_file
from .errors import BarclaysError
from .officials import external
from .officials.base import Ctx, result
from .spec import bout_overrides, check_privacy


def derive_eligibility(results: list, candidates: list, baseline: str | None):
    """Eligibility from official results alone. `candidates` is [(id, content_hash)] in bout order.

    Kept as a pure function so `bc verify` can recompute it from the objects in a run's ledger and compare it with
    what the run recorded.
    """
    eligibility = {}
    baseline_fails_target = False
    for cid, content_hash in candidates:
        is_base = cid == baseline
        dq, inc = [], []
        for res in (r for r in results if r["candidate_id"] == cid):
            decisive = res["authority"] == "disqualify" and (res["applies_to"] == "all" or not is_base)
            if not decisive:
                if is_base and res["authority"] == "disqualify" and res["status"] == "fail":
                    baseline_fails_target = True
                continue
            if res["status"] == "fail":
                dq.append(f"{res['official_id']}: {res['summary']}")
            elif res["status"] == "unverified":
                inc.append(f"{res['official_id']}: {res['summary']}")
        status = "disqualified" if dq else ("incomplete" if inc else "eligible")
        eligibility[cid] = {"status": status, "reasons": dq or inc, "content_hash": content_hash,
                            "is_baseline": is_base}
    return eligibility, baseline_fails_target


def attribute_limits(results: list) -> None:
    """Decide whose fault an unattributed timeout or oversize answer was, by looking across candidates.

    One official run cannot always say whether a harness limit was hit because of the suite or because of the
    candidate. Across candidates it often can:

      unattributed_timeout  The suite ran out of time while the candidate was not being waited on. If the same
                            suite, under the same official and budget, FINISHED for another candidate in this run,
                            the suite is not too slow; the candidate is, and it has failed.
      unattributed_limit    An answer was over the size limit. If another candidate PASSED this suite, correct
                            answers fit the limit, and the oversize one has failed. (Finishing is not enough here:
                            a wrong short answer says nothing about how long a right one is.)

    Otherwise the result stays 'unverified': missing evidence is not a failure. That leaves one known gap: a wrong
    candidate with no competitor that got through can end 'unverified' instead of 'fail'. It cannot end 'pass'.
    """
    by_official: dict = {}
    for res in results:
        by_official.setdefault(res["official_id"], []).append(res)
    for group in by_official.values():
        clean = [r for r in group if r["status"] in ("pass", "fail")
                 and (r.get("receipt") or {}).get("result_authenticated")
                 and not (r.get("receipt") or {}).get("timed_out")]
        passed = [r for r in clean if r["status"] == "pass"]
        for res in group:
            receipt = res.get("receipt") or {}
            if res["status"] != "unverified":
                continue
            if receipt.get("unattributed_timeout") and clean:
                slowest = max(float((r.get("metrics") or {}).get("seconds") or 0.0) for r in clean)
                why = (f"suite '{receipt.get('suite')}' ran out of time for this candidate in two attempts, and "
                       f"finished for {len(clean)} other candidate(s) in this run (slowest: {slowest:g} s). The "
                       "suite is not too slow; the candidate is")
                fid, others = "TIMEOUT-RELATIVE", clean
            elif receipt.get("unattributed_limit") and passed:
                why = (f"{res['summary'].split('. Either')[0]}, and {len(passed)} other candidate(s) passed this "
                       "suite within the limit. Correct answers fit; this one does not")
                fid, others = "ANSWER-TOO-LONG", passed
            else:
                continue
            res["status"], res["summary"] = "fail", why
            res["findings"] = [{"id": fid, "severity": "critical", "claim": why,
                                "locator": f"suite:{receipt.get('suite')}",
                                "evidence": {"compared_with": [r["candidate_id"] for r in others]}}]
            receipt["reclassified"] = "unverified -> fail by comparison across candidates"


attribute_timeouts = attribute_limits      # the earlier name, kept for callers and tests


def run_weigh_in(bout: dict, event: dict, run_dir: str, ledger) -> dict:
    check_privacy(f"event '{event['event_id']}'", event["privacy"]["allowed_sensitivity"], bout["sensitivity"])
    overrides = bout.get("_overrides") or bout_overrides(bout, event)
    scratch = tempfile.mkdtemp(prefix="weighin-", dir=run_dir)
    baseline = bout.get("baseline")
    results = []
    # One table for the whole weigh-in: the copy pinned when the manifest was written, or one loaded now.
    table = bout.get("_plugins") or external.active_plugins()
    for cfg in event.get("officials", []):
        name = cfg["official"]
        # Built-in first; then the venue's plug-in table; else an official that reports 'unverified' because no
        # plug-in is installed. A missing plug-in is loud (PLUGIN_MISSING in the verdict) and never a pass.
        fn, cleared, _origin = external.resolve(name, table)
        check_privacy(f"official '{name}'", cleared, bout["sensitivity"])
        params = dict(cfg.get("params", {}))
        params.update(overrides["officials"].get(cfg["id"], {}))
        for cand in bout["candidates"]:
            ctx = Ctx(bout=bout, event=event, cfg=cfg, candidate=cand, is_baseline=(cand["id"] == baseline),
                      workdir=scratch, params=params)
            try:
                res = fn(ctx)
            except Exception as exc:  # noqa: BLE001  an official crashing is a harness failure, not a verdict
                res = result(ctx, name, "?", "deterministic", "unverified",
                             f"official crashed: {type(exc).__name__}: {exc}",
                             receipt={"traceback_tail": traceback.format_exc()[-600:]})
            results.append(res)
    attribute_limits(results)
    for res in results:
        sha = ledger.put_json(res)
        ledger.append("official_result", {"official_id": res["official_id"], "candidate_id": res["candidate_id"],
                                          "status": res["status"], "authority": res["authority"]},
                      {"result": sha})
        res["_object"] = sha
    try:
        os.rmdir(scratch)
    except OSError:
        pass

    eligibility, baseline_fails_target = derive_eligibility(
        results, [(c["id"], c["content_hash"]) for c in bout["candidates"]], baseline)

    plugin_table = None
    if table.get("path"):
        # The table was read once, before any plug-in ran. If the file is different now, something rewrote it
        # while the officials were running. It changed nothing in this run, and it is worth saying.
        try:
            now = sha256_file(table["path"])
        except OSError:
            now = None
        plugin_table = {"sha256": table["sha256"], "changed_during_weigh_in": now != table["sha256"]}
    summary = {
        "eligibility": eligibility,
        "baseline_fails_target": baseline_fails_target,
        "results": results,
        "plugin_table": plugin_table,
    }
    sha = ledger.put_json({"eligibility": eligibility, "baseline_fails_target": baseline_fails_target,
                           "result_objects": [r["_object"] for r in results], "plugin_table": plugin_table})
    ledger.append("weigh_in", {cid: e["status"] for cid, e in eligibility.items()}, {"weigh_in": sha})
    return summary


def findings_and_leads(weigh_in: dict, candidate_id: str):
    """(objective findings, heuristic leads) for one candidate, each tagged with the official that produced it."""
    findings, leads = [], []
    for res in weigh_in["results"]:
        if res["candidate_id"] != candidate_id:
            continue
        tag = f"{res['official']}@{res['official_version']}"
        for f in res["findings"]:
            findings.append(dict(f, official_id=res["official_id"], tool=tag))
        for item in res["leads"]:
            leads.append(dict(item, official_id=res["official_id"], tool=tag))
    return findings, leads
