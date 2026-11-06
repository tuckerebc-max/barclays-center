"""Run one bout: manifest, weigh-in, bracket, verdict, report. Every step is written to the run ledger."""
from __future__ import annotations

import os

from . import __version__
from .bracket import advance_bracket, controller_identity, find_atr, find_python, run_bracket
from .canon import read_json, sha256_file, write_json
from .errors import BarclaysError, Refusal
from .ledger import TREE_FORMAT, Ledger, run_tree
from .report import render_report
from .spec import bout_overrides, load_bout, load_events
from .verdict import build_verdict
from .officials.external import active_plugins
from .weighin import run_weigh_in


def _load(bout_dir: str, events_dir: str):
    bout = load_bout(bout_dir)
    events = load_events(events_dir)
    event = events.get(bout["event"])
    if event is None:
        raise BarclaysError(f"bout names an unknown event '{bout['event']}'. Known: {', '.join(sorted(events))}")
    if event["status"] not in ("runnable", "officials_runnable"):
        raise Refusal(f"event '{event['event_id']}' is specified but not runnable yet: {event.get('notes', '')}")
    bout["_overrides"] = bout_overrides(bout, event)
    return bout, event


def open_run(out_dir: str) -> Ledger:
    if os.path.exists(out_dir) and os.listdir(out_dir):
        raise Refusal(f"run directory is not empty: {out_dir}. Runs are append-only; choose a new directory "
                      "rather than overwriting evidence.")
    os.makedirs(out_dir, exist_ok=True)
    return Ledger(out_dir)


def write_manifest(bout: dict, event: dict, ledger: Ledger, out_dir: str) -> None:
    manifest = {
        "barclays_version": __version__,
        "bout_id": bout["bout_id"], "bout_sha256": bout["_sha256"],
        "event_id": event["event_id"], "event_sha256": event["_sha256"],
        "sensitivity": bout["sensitivity"],
        "candidates": [{"id": c["id"], "content_hash": c["content_hash"],
                        "files": [{"path": f["path"], "sha256": f["sha256"]} for f in c["files"]]}
                       for c in bout["candidates"]],
        "sources": {k: ({"path": v["path"], "sha256": v["sha256"]} if isinstance(v, dict)
                        else [{"path": x["path"], "sha256": x["sha256"]} for x in v])
                    for k, v in bout["_sources"].items()},
    }
    table = active_plugins()
    # Pinned here, once, for the whole run: every official of this run is resolved against this copy, so a table
    # rewritten while the run is under way changes nothing in it (fourth review, R4-02).
    bout["_plugins"] = table
    if table["path"]:
        # Which sibling officials this venue had installed for the run: the table by hash, each entry by name.
        manifest["plugins"] = {"table_sha256": table["sha256"],
                               "officials": {name: {"repo": spec.get("repo"), "argv": spec["argv"]}
                                             for name, spec in sorted(table["officials"].items())}}
    write_json(os.path.join(out_dir, "manifest.json"), manifest)
    ledger.append("manifest", {"bout_id": bout["bout_id"], "event_id": event["event_id"],
                               "candidates": len(bout["candidates"])},
                  {"manifest": ledger.put_file(os.path.join(out_dir, "manifest.json")),
                   "event_card": ledger.put_file(event["_path"]),
                   "bout": ledger.put_file(os.path.join(bout["_dir"], "bout.json"))})


# What the venue itself writes at the top of a run directory. Anything else found there at seal time was put there
# by something else (a plug-in, a person); it is sealed like everything else, and the seal says it was unexpected.
RUN_ENTRIES = {"ledger.jsonl", "objects", "manifest.json", "verdict.json", "REPORT.md", "bracket",
               "bracket-plan.json", "shadow-bracket", "panel", "panel-attached.json"}


def seal(ledger: Ledger, run_dir: str) -> dict:
    """Close a finished run. Nothing may follow a seal; `bc verify` checks the files against it."""
    files = {}
    for name in ("manifest.json", "verdict.json", "REPORT.md"):
        path = os.path.join(run_dir, name)
        if os.path.isfile(path):
            files[name] = sha256_file(path)
    tree = run_tree(run_dir)        # every file a reader might open, not only the three above
    unexpected = sorted(n for n in os.listdir(run_dir) if n not in RUN_ENTRIES and n != "__pycache__")
    return ledger.append("seal", {"events_before_seal": ledger.seq, "files": files, "tree_files": len(tree),
                                  "tree_format": TREE_FORMAT, "unexpected_entries": unexpected[:50],
                                  "note": "the run is finished; nothing may follow this event"},
                         {"tree": ledger.put_json(tree)})


def run_bout(bout_dir: str, out_dir: str, events_dir: str, judges: str = "sim", atr: str | None = None,
             atr_python: str | None = None, seed: int | None = None, shadow: bool = False,
             behaviors: dict | None = None, panel: dict | None = None, panel_from: str | None = None) -> dict:
    """Run a bout end to end and return the verdict.

    judges: 'sim' (the controller's simulator, driven by the bout's sim/truth.json; a dry run), 'real' (a model
    registry must be supplied) or 'none' (weigh-in only).
    shadow: also run the same judges over every candidate with no weigh-in and no gates, to measure what judging
    alone would have chosen. Diagnostic only.
    """
    if judges not in ("sim", "real", "none"):
        raise BarclaysError("judges must be 'sim', 'real' or 'none'")
    bout, event = _load(bout_dir, events_dir)
    bracket_available = event["status"] == "runnable"
    if not bracket_available:
        judges = "none"         # this event has no model bracket in this version; survivors go to people
    ledger = open_run(out_dir)
    write_manifest(bout, event, ledger, out_dir)
    weigh_in = run_weigh_in(bout, event, out_dir, ledger)
    if panel_from:
        # A panel run earlier on these exact bytes travels with this verdict (advisory; see lenses.attach_panel).
        from .lenses import attach_panel
        panel = attach_panel(panel_from, bout)
        write_json(os.path.join(out_dir, "panel-attached.json"), panel)
        ledger.append("panel_attached", {"source_ledger_head": panel["_source_run"]["ledger_head"],
                                         "valid_results": panel.get("valid_results")},
                      {"panel": ledger.put_file(os.path.join(out_dir, "panel-attached.json"))})

    elig = weigh_in["eligibility"]
    baseline = bout.get("baseline")
    by_id = {c["id"]: c for c in bout["candidates"]}
    entrants = [by_id[cid] for cid in by_id if elig[cid]["status"] == "eligible"]
    eligible_challengers = [c for c in entrants if c["id"] != baseline]
    bracket_baseline = baseline if baseline and elig[baseline]["status"] == "eligible" else None

    sim_truth = None
    truth_path = os.path.join(bout["_dir"], "sim", "truth.json")
    if judges == "sim":
        if not os.path.isfile(truth_path):
            raise Refusal("simulated judges need the bout's sim/truth.json. A simulator has no opinion of its own; "
                          "the perceptions it is given are part of the record.")
        sim_truth = read_json(truth_path)
        if behaviors:
            merged = dict(sim_truth.get("behaviors") or {})
            for alias, extra in behaviors.items():
                merged[alias] = dict(merged.get(alias, {}), **extra)
            sim_truth = dict(sim_truth, behaviors=merged)
    run_seed = int(seed if seed is not None else (sim_truth or {}).get("seed", 0))

    bracket = shadow_result = controller = None
    no_bracket_reason = ""
    stages = event["stages"]
    if judges == "none" or "bracket" not in stages:
        no_bracket_reason = ("this event has no model bracket in this version: the officials decide who is "
                             "eligible and people decide among the survivors" if not bracket_available else
                             "weigh-in only: no judging was requested" if judges == "none" else
                             "this event has no bracket stage")
    elif eligible_challengers and len(entrants) >= 2:
        atr_path, python = find_atr(atr), find_python(atr_python)
        controller = controller_identity(atr_path)
        bracket = run_bracket(bout, event, entrants, bracket_baseline, os.path.join(out_dir, "bracket"), run_seed,
                              judges, sim_truth, atr_path, python)
        write_json(os.path.join(out_dir, "bracket-plan.json"), bracket["plan"])
        if bracket["decision_path"]:
            ledger.append("bracket_decision", {"status": bracket["decision"]["decision"]["status"],
                                               "campaign_id": bracket["decision"].get("campaign_id")},
                          {"decision": ledger.put_file(bracket["decision_path"]),
                           "plan": ledger.put_json(bracket["plan"])})
        else:
            ledger.append("bracket_waiting", {"waiting_on_host": bracket["run"].get("waiting_on_host"),
                                              "work_index": "bracket/native/work/INDEX.md"},
                          {"plan": ledger.put_json(bracket["plan"])})
    elif eligible_challengers:
        no_bracket_reason = "one eligible candidate and no eligible comparator: nothing to compare it against"

    if shadow and judges == "sim" and len(bout["candidates"]) >= 2:
        atr_path, python = find_atr(atr), find_python(atr_python)
        shadow_result = run_bracket(bout, event, list(bout["candidates"]), baseline,
                                    os.path.join(out_dir, "shadow-bracket"), run_seed, judges, sim_truth, atr_path,
                                    python, with_gates=False, tag="-shadow")
        if shadow_result["decision_path"]:
            ledger.append("shadow_decision", {"status": shadow_result["decision"]["decision"]["status"],
                                              "authority": "none (diagnostic)"},
                          {"decision": ledger.put_file(shadow_result["decision_path"])})

    verdict = build_verdict(bout, event, weigh_in, bracket, shadow_result, panel, judges, controller,
                            no_bracket_reason)
    verdict["seed"] = run_seed
    vsha = write_json(os.path.join(out_dir, "verdict.json"), verdict)
    report = render_report(bout, event, weigh_in, verdict)
    with open(os.path.join(out_dir, "REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write(report)
    ev = ledger.append("verdict", {"status": verdict["status"], "recommended": verdict["recommended"],
                                   "flags": verdict["flags"], "verdict_sha256": vsha},
                       {"verdict": ledger.put_file(os.path.join(out_dir, "verdict.json")),
                        "report": ledger.put_file(os.path.join(out_dir, "REPORT.md"))})
    if bracket is None or bracket.get("decision") is not None:
        ev = seal(ledger, out_dir)          # a run still waiting on judges stays open for `resume`
    verdict["_ledger_head"] = ev["hash"]
    verdict["_weigh_in"] = weigh_in
    return verdict


def load_weigh_in(run_dir: str) -> dict:
    """Rebuild the weigh-in from the run's own ledger objects (the last weigh_in event and the results it names)."""
    import json
    last = None
    with open(os.path.join(run_dir, "ledger.jsonl"), "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                event = json.loads(line)
                if event["kind"] == "weigh_in":
                    last = event
    if last is None:
        raise BarclaysError(f"no weigh-in recorded in {run_dir}")
    doc = read_json(os.path.join(run_dir, "objects", last["refs"]["weigh_in"]))
    results = []
    for sha in doc["result_objects"]:
        res = read_json(os.path.join(run_dir, "objects", sha))
        res["_object"] = sha
        results.append(res)
    return {"eligibility": doc["eligibility"], "baseline_fails_target": doc["baseline_fails_target"],
            "results": results, "plugin_table": doc.get("plugin_table")}


def resume_bout(bout_dir: str, run_dir: str, events_dir: str, atr: str | None = None,
                atr_python: str | None = None) -> dict:
    """Continue a run whose bracket is waiting on real judges.

    The host answers the controller's packets (bracket/native/work/INDEX.md, one fresh context per packet), then
    calls this. It imports the results, steps the controller, and when the controller has decided, writes the
    verdict. The weigh-in is not rerun: it is read back from the ledger, and the bout's hashes must still match.
    """
    bout, event = _load(bout_dir, events_dir)
    manifest = read_json(os.path.join(run_dir, "manifest.json"))
    if manifest["bout_sha256"] != bout["_sha256"] or manifest["event_sha256"] != event["_sha256"]:
        raise Refusal("the bout or its event card changed since this run started; a changed contract is a new run")
    for cand in bout["candidates"]:
        recorded = next((c["content_hash"] for c in manifest["candidates"] if c["id"] == cand["id"]), None)
        if recorded != cand["content_hash"]:
            raise Refusal(f"candidate '{cand['id']}' changed since this run started; a changed candidate is a new one")
    ledger = Ledger(run_dir)
    weigh_in = load_weigh_in(run_dir)
    campaign_dir = os.path.join(run_dir, "bracket")
    if not os.path.isdir(campaign_dir):
        raise BarclaysError("this run has no bracket to resume")
    atr_path, python = find_atr(atr), find_python(atr_python)
    bracket = advance_bracket(campaign_dir, atr_path, python)
    plan_path = os.path.join(run_dir, "bracket-plan.json")
    bracket["plan"] = read_json(plan_path) if os.path.isfile(plan_path) else {}
    if bracket["decision"] is None:
        ledger.append("bracket_waiting", {"waiting_on_host": bracket["run"].get("waiting_on_host")}, {})
        return {"waiting": True, "waiting_on_host": bracket["run"].get("waiting_on_host"),
                "work_index": os.path.join(campaign_dir, "native", "work", "INDEX.md"), "run": bracket["run"]}
    ledger.append("bracket_decision", {"status": bracket["decision"]["decision"]["status"],
                                       "campaign_id": bracket["decision"].get("campaign_id")},
                  {"decision": ledger.put_file(bracket["decision_path"])})
    attached = os.path.join(run_dir, "panel-attached.json")
    panel = read_json(attached) if os.path.isfile(attached) else None
    verdict = build_verdict(bout, event, weigh_in, bracket, None, panel, "real", controller_identity(atr_path))
    vsha = write_json(os.path.join(run_dir, "verdict.json"), verdict)
    with open(os.path.join(run_dir, "REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write(render_report(bout, event, weigh_in, verdict))
    ev = ledger.append("verdict", {"status": verdict["status"], "recommended": verdict["recommended"],
                                   "flags": verdict["flags"], "verdict_sha256": vsha},
                       {"verdict": ledger.put_file(os.path.join(run_dir, "verdict.json")),
                        "report": ledger.put_file(os.path.join(run_dir, "REPORT.md"))})
    ev = seal(ledger, run_dir)
    verdict["_ledger_head"] = ev["hash"]
    verdict["_weigh_in"] = weigh_in
    return verdict
