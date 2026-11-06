"""The bracket: hand the eligible candidates to the existing tournament controller.

Barclays does not schedule matches, reconcile judging orders, count family votes or apply a decision rule. The
adversarial-tournament-review controller (atr/1) already does all of that under tested invariants. This module
compiles a bout into an ATR campaign directory, runs the controller as a subprocess and reads its decision record.

The boundary is a file contract: campaign directory in, `reports/decision.json` out. Nothing is imported from the
controller, so the two repositories version independently.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from .canon import sha256_file, write_json
from .spec import bout_overrides
from .errors import BarclaysError, Refusal

ATR_RELATIVE = os.path.join("skills", "adversarial-tournament-review", "scripts", "atr.py")

# Simulated judges for dry runs: four aliases in three families, so the controller's family quorum is exercised.
SIM_MODELS = [("sim-alpha", "sim-family-a"), ("sim-beta", "sim-family-b"), ("sim-gamma", "sim-family-c"),
              ("sim-delta", "sim-family-a")]


def find_atr(explicit: str | None = None) -> str:
    """Locate the controller's atr.py. Order: explicit path, BARCLAYS_ATR, sibling checkouts."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tried = []
    for cand in (explicit, os.environ.get("BARCLAYS_ATR"),
                 os.path.join(os.path.dirname(here), "adversarial-tournament-review"),
                 os.path.join(os.path.expanduser("~"), "Documents", "GitHub", "adversarial-tournament-review")):
        if not cand:
            continue
        path = cand if cand.endswith(".py") else os.path.join(cand, ATR_RELATIVE)
        tried.append(path)
        if os.path.isfile(path):
            return os.path.abspath(path)
    raise Refusal("the tournament controller (adversarial-tournament-review) was not found. Barclays does not "
                  "carry a second controller. Pass --atr or set BARCLAYS_ATR. Tried: " + "; ".join(tried))


def find_python(explicit: str | None = None) -> str:
    """An interpreter the controller runs on.

    The controller does not import on Python 3.13 yet. Until it does, Barclays runs it on 3.11 or 3.12.
    """
    cand = explicit or os.environ.get("BARCLAYS_ATR_PYTHON")
    if cand:
        return cand
    if sys.version_info < (3, 13):
        return sys.executable
    for name in ("python3.12", "python3.11"):
        for base in (None, "/usr/bin", "/usr/local/bin"):
            path = shutil.which(name) if base is None else os.path.join(base, name)
            if path and os.path.isfile(path):
                return path
    raise Refusal("this interpreter is Python 3.13+, on which the controller does not import yet. "
                  "Install Python 3.11 or 3.12, or pass --atr-python.")


def controller_identity(atr: str) -> dict:
    """Which controller build produced the decision: file hashes plus the git commit when available."""
    pkg = os.path.join(os.path.dirname(atr), "atr")
    files = {}
    for name in ("records.py", "aggregate.py", "decide.py", "engine.py", "canon.py"):
        path = os.path.join(pkg, name)
        if os.path.isfile(path):
            files[name] = sha256_file(path)
    commit = None
    try:
        out = subprocess.run(["git", "-C", os.path.dirname(atr), "rev-parse", "HEAD"], capture_output=True,
                             text=True, timeout=10)
        if out.returncode == 0:
            commit = out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return {"name": "adversarial-tournament-review", "schema": "atr/1", "commit": commit, "files": files}


def _toml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def compile_campaign(bout: dict, event: dict, entrants: list, baseline_id: str | None, campaign_dir: str,
                     seed: int, judges: str, sim_truth: dict | None, with_gates: bool, tag: str) -> str | None:
    """Write an ATR campaign for `entrants`. Returns the sim-truth path when simulated judges are used."""
    if os.path.exists(campaign_dir):
        raise BarclaysError(f"campaign directory already exists: {campaign_dir}")
    inputs = os.path.join(campaign_dir, "inputs")
    os.makedirs(os.path.join(inputs, "candidates"))
    os.makedirs(os.path.join(inputs, "evidence"))
    # A bout may override the bracket controls its event card lists under format.bracket.bout_may_set (for
    # example fewer judges per match for a costly real panel). The override is part of bout.json, so it is hashed
    # with the bout, and it is flagged in the verdict.
    fmt = dict((event.get("format") or {}).get("bracket") or {})
    fmt.pop("bout_may_set", None)
    fmt.update((bout.get("_overrides") or bout_overrides(bout, event))["bracket"])

    manifest = []
    for cand in entrants:
        cdir = os.path.join(inputs, "candidates", cand["id"])
        os.makedirs(cdir)
        files = []
        for f in cand["files"]:
            shutil.copyfile(f["abs"], os.path.join(cdir, f["path"]))
            files.append({"path": f["path"], "source": f"candidates/{cand['id']}/{f['path']}"})
        entry = {"id": cand["id"], "files": files}
        if cand["id"] == baseline_id:
            entry["is_baseline"] = True
        # Authorship is passed so the controller can keep a model family off its own candidate's panel.
        for key in ("author", "author_family"):
            if cand.get(key):
                entry[key] = cand[key]
        manifest.append(entry)
    write_json(os.path.join(inputs, "candidates.json"), {"candidates": manifest})

    items = []
    for key in fmt.get("evidence_sources", []):
        src = bout["_sources"].get(key)
        for part in (src if isinstance(src, list) else [src] if src else []):
            paths = [part["abs"]] if os.path.isfile(part["abs"]) else sorted(
                os.path.join(part["abs"], n) for n in os.listdir(part["abs"]) if os.path.isfile(
                    os.path.join(part["abs"], n)))
            for path in paths:
                name = f"{len(items) + 1:02d}-{os.path.basename(path)}"
                shutil.copyfile(path, os.path.join(inputs, "evidence", name))
                items.append({"id": f"ev{len(items) + 1}", "source": f"evidence/{name}", "description": key})
    write_json(os.path.join(inputs, "evidence.json"), {"version": 1, "items": items, "known_answers": {}})

    criteria = [{k: c[k] for k in ("id", "definition", "weight", "anchors") if k in c} for c in event["criteria"]]
    gates = [{"id": g["id"], "definition": g["definition"], "check": "model"}
             for g in event.get("model_gates", [])] if with_gates else []
    rubric = {"id": f"{event['event_id']}-r1", "version": 1, "aggregation": "weighted",
              "material_improvement": float((event.get("abstention") or {}).get("material_improvement", 5.0)),
              "criteria": criteria, "gates": gates}
    write_json(os.path.join(inputs, "rubric.json"), rubric)

    sim_path = None
    if judges == "sim":
        models = [{"alias": a, "model_id": a, "provider": "sim", "family": fam, "lane_class": "sim",
                   "modalities": ["text", "image", "execution"],
                   "calibration": {"status": "uncalibrated", "date": "2026-11-04",
                                   "notes": "simulator; not a model"}} for a, fam in SIM_MODELS]
        write_json(os.path.join(inputs, "registry.json"), {"models": models})
        truth = sim_truth or {}
        ids = {c["id"] for c in entrants}
        doc = {"seed": seed, "behaviors": truth.get("behaviors", {}),
               "truth": {cid: t for cid, t in (truth.get("truth") or {}).items() if cid in ids}}
        sim_path = os.path.join(campaign_dir, "sim-truth.json")
        write_json(sim_path, doc)
    else:
        # The judge registry is a bout source, so the exact panel is hashed with everything else.
        src = bout["_sources"].get(fmt.get("registry_source", "judge_registry"))
        if not isinstance(src, dict) or not os.path.isfile(src["abs"]):
            raise Refusal("real judges need a model registry declared as the bout source 'judge_registry' "
                          "(the controller's registry format). None was supplied; nothing was sent to any model.")
        shutil.copyfile(src["abs"], os.path.join(inputs, "registry.json"))

    campaign_id = f"{bout['bout_id']}{tag}"[:64]
    lines = [
        f"campaign_id = {_toml_str(campaign_id)}",
        f"task_unit_id = {_toml_str(bout['bout_id'][:64])}",
        f"purpose = {_toml_str(bout['purpose'])}",
        f"audience = {_toml_str(bout['audience'])}",
        'artifact_type = "text"',
        f"profile = {_toml_str(fmt.get('profile', 'light'))}",
    ]
    if baseline_id:
        lines.append(f"baseline_id = {_toml_str(baseline_id)}")
    lines += ["", "[tournament]", f"seed = {int(seed)}"]
    for key in ("judges_per_match", "grade_judges", "minimum_family_quorum", "pairing_rounds", "finalists",
                "final_judges_per_match", "tournaments_per_cycle"):
        if key in fmt:
            lines.append(f"{key} = {int(fmt[key])}")
    if fmt.get("allow_single_family"):
        lines.append("allow_single_family = true")
    lines += ["", "[limits]", f"max_model_calls = {int(fmt.get('max_model_calls', 400))}", ""]
    routing = fmt.get("routing") or {}
    if routing:
        lines.append("[routing]")
        for pool, aliases in routing.items():
            lines.append(f"{pool} = [" + ", ".join(_toml_str(a) for a in aliases) + "]")
        lines.append("")
    with open(os.path.join(campaign_dir, "campaign.toml"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return sim_path


def _atr(python: str, atr: str, args: list, timeout: float = 600) -> dict:
    proc = subprocess.run([python, "-B", atr] + args, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise BarclaysError(f"controller command {args[0]!r} failed (exit {proc.returncode}): "
                            f"{(proc.stderr or proc.stdout)[-600:]}")
    try:
        return json.loads(proc.stdout)
    except ValueError as exc:
        raise BarclaysError(f"controller command {args[0]!r} did not print JSON: {exc}") from exc


def advance_bracket(campaign_dir: str, atr: str, python: str) -> dict:
    """Continue a campaign that is waiting on a native host: import the host's results, then step again.

    Returns {'run', 'decision', 'decision_path', 'campaign_dir'}; 'decision' is None while judges are still owed.
    """
    _atr(python, atr, ["import-results", campaign_dir])
    run = _atr(python, atr, ["run", campaign_dir])
    decision_path = os.path.join(campaign_dir, "reports", "decision.json")
    decision = None
    if os.path.isfile(decision_path) and run.get("done", True) and not run.get("waiting_on_host"):
        with open(decision_path, "r", encoding="utf-8") as fh:
            decision = json.load(fh)
    return {"run": run, "decision": decision, "decision_path": decision_path if decision else None,
            "campaign_dir": campaign_dir}


def run_bracket(bout: dict, event: dict, entrants: list, baseline_id: str | None, campaign_dir: str, seed: int,
                judges: str, sim_truth: dict | None, atr: str, python: str, with_gates: bool = True,
                tag: str = "") -> dict:
    """Compile, plan and run one campaign. Returns {'plan', 'decision', 'decision_path', 'campaign_dir'}."""
    sim_path = compile_campaign(bout, event, entrants, baseline_id, campaign_dir, seed, judges, sim_truth,
                                with_gates, tag)
    plan = _atr(python, atr, ["plan", campaign_dir])
    args = ["run", campaign_dir] + (["--sim-truth", sim_path] if sim_path else [])
    run = _atr(python, atr, args)
    decision_path = os.path.join(campaign_dir, "reports", "decision.json")
    if not os.path.isfile(decision_path) or run.get("waiting_on_host"):
        # A native-host run stops here, waiting for judges. That is a state, not an error.
        return {"plan": plan, "run": run, "decision": None, "decision_path": None, "campaign_dir": campaign_dir}
    with open(decision_path, "r", encoding="utf-8") as fh:
        decision = json.load(fh)
    return {"plan": plan, "run": run, "decision": decision, "decision_path": decision_path,
            "campaign_dir": campaign_dir}
