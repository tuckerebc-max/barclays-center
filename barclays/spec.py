"""Event cards, bouts and the privacy boundary.

An EVENT CARD is the reusable tournament specification for one genre: objective, audience, the officials that run
before judging (with their authority), the judged criteria, the lenses on the panel, the evidence required, when
to abstain and when a human decides.

A BOUT is one contest under an event card: the exact candidates and source artifacts for one task.

Validation is strict and hand-written (standard library only). Unknown top-level keys are rejected so a typo cannot
silently disable a rule.
"""
from __future__ import annotations

import os
import re
from typing import Any

from . import BOUT_SCHEMA, EVENT_SCHEMA, SENSITIVITY, STATUSES
from .canon import read_json, sha256_file, tree_hash
from .errors import BarclaysError, Refusal

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
AUTHORITIES = ("disqualify", "advise")
APPLIES = ("all", "challengers")
# runnable: weigh-in, panel and bracket all run. officials_runnable: the weigh-in and the panel run (through
# plug-ins where the card names them); the event has no model bracket in this version, so survivors go to people.
# specified: a design, not yet runnable.
EVENT_STATUS = ("runnable", "officials_runnable", "specified")
STAGES = ("weigh_in", "panel", "bracket", "human_review")

EVENT_KEYS = {
    "schema", "event_id", "title", "genre", "status", "objective", "audience", "artifact_type", "candidate_inputs",
    "stages", "officials", "criteria", "model_gates", "lenses", "evidence_required", "hard_disqualifiers",
    "judge_qualifications", "format", "abstention", "human_decides_when", "human_evidence_boundary", "privacy",
    "notes",
}
BOUT_KEYS = {
    "schema", "bout_id", "event", "purpose", "audience", "sensitivity", "baseline", "candidates", "sources",
    "params", "notes",
}
HUMAN_RULE_RE = re.compile(r"^(always|open_critical_leads|unverified_allegations|simulated_judges"
                           r"|model_gate_exclusion"
                           r"|on_status:[A-Z_]+|sensitivity_not_in:[a-z,]+)$")


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise BarclaysError(msg)


def _str(d: dict, key: str, where: str, required: bool = True) -> str:
    v = d.get(key)
    if v is None and not required:
        return ""
    _need(isinstance(v, str) and v.strip() != "", f"{where}: '{key}' must be a non-empty string")
    return v


def load_event(path: str) -> dict:
    """Load and validate one event card. Returns the card with '_path' and '_sha256' added."""
    card = read_json(path)
    where = f"event card {os.path.basename(path)}"
    _need(isinstance(card, dict), f"{where}: must be a JSON object")
    extra = set(card) - EVENT_KEYS
    _need(not extra, f"{where}: unknown keys {sorted(extra)}")
    _need(card.get("schema") == EVENT_SCHEMA, f"{where}: schema must be {EVENT_SCHEMA}")
    _need(ID_RE.match(_str(card, "event_id", where)) is not None, f"{where}: bad event_id")
    for key in ("title", "genre", "objective", "audience", "artifact_type"):
        _str(card, key, where)
    _need(card.get("status") in EVENT_STATUS, f"{where}: status must be one of {EVENT_STATUS}")
    stages = card.get("stages")
    _need(isinstance(stages, list) and stages and all(s in STAGES for s in stages),
          f"{where}: stages must be a non-empty list drawn from {STAGES}")

    officials = card.get("officials", [])
    _need(isinstance(officials, list), f"{where}: officials must be a list")
    seen = set()
    for o in officials:
        _need(isinstance(o, dict), f"{where}: each official must be an object")
        oid = _str(o, "id", where)
        _need(ID_RE.match(oid) is not None and oid not in seen, f"{where}: official id '{oid}' invalid or repeated")
        seen.add(oid)
        _str(o, "official", f"{where} official {oid}")
        _need(o.get("authority") in AUTHORITIES, f"{where} official {oid}: authority must be one of {AUTHORITIES}")
        _need(o.get("applies_to", "all") in APPLIES, f"{where} official {oid}: applies_to must be one of {APPLIES}")
        _need(isinstance(o.get("params", {}), dict), f"{where} official {oid}: params must be an object")
        may = o.get("bout_may_set", [])
        _need(isinstance(may, list) and all(isinstance(k, str) for k in may),
              f"{where} official {oid}: bout_may_set must be a list of parameter names")
        extra_o = set(o) - {"id", "official", "authority", "applies_to", "params", "why", "bout_may_set"}
        _need(not extra_o, f"{where} official {oid}: unknown keys {sorted(extra_o)}")

    criteria = card.get("criteria", [])
    _need(isinstance(criteria, list), f"{where}: criteria must be a list")
    if card["status"] == "runnable" and "bracket" in stages:
        _need(len(criteria) >= 1, f"{where}: a runnable event with a bracket needs judged criteria")
        total = sum(float(c.get("weight", 0)) for c in criteria)
        _need(abs(total - 1.0) < 1e-9, f"{where}: criterion weights must sum to 1 (got {total})")
    for c in criteria:
        _need(isinstance(c, dict) and ID_RE.match(str(c.get("id", ""))) is not None, f"{where}: bad criterion id")
        _str(c, "definition", f"{where} criterion {c.get('id')}")

    for rule in card.get("human_decides_when", []):
        _need(isinstance(rule, str) and HUMAN_RULE_RE.match(rule) is not None,
              f"{where}: unknown human_decides_when rule '{rule}'")
        if rule.startswith("on_status:"):
            _need(rule.split(":", 1)[1] in STATUSES, f"{where}: rule '{rule}' names an unknown status")

    privacy = card.get("privacy", {})
    allowed = privacy.get("allowed_sensitivity", [])
    _need(isinstance(allowed, list) and allowed and all(a in SENSITIVITY for a in allowed),
          f"{where}: privacy.allowed_sensitivity must be a non-empty list drawn from {SENSITIVITY}")

    card["_path"] = os.path.abspath(path)
    card["_sha256"] = sha256_file(path)
    return card


def load_events(events_dir: str) -> dict:
    """All event cards in a directory, keyed by event_id."""
    out = {}
    for name in sorted(os.listdir(events_dir)):
        if name.endswith(".json"):
            card = load_event(os.path.join(events_dir, name))
            _need(card["event_id"] not in out, f"duplicate event_id {card['event_id']}")
            out[card["event_id"]] = card
    return out


def _resolve(base: str, rel: str, where: str) -> str:
    """Resolve a bout-relative path. Absolute paths and escapes from the bout directory are refused."""
    _need(isinstance(rel, str) and rel != "", f"{where}: path must be a non-empty string")
    if os.path.isabs(rel) or re.match(r"^[A-Za-z]:[\\/]", rel):
        raise Refusal(f"{where}: absolute path refused ({rel!r}); bout inputs must live inside the bout directory")
    full = os.path.realpath(os.path.join(base, rel))
    root = os.path.realpath(base)
    if not (full == root or full.startswith(root + os.sep)):
        raise Refusal(f"{where}: path escapes the bout directory ({rel!r})")
    _need(os.path.exists(full), f"{where}: not found: {rel}")
    _refuse_links(os.path.abspath(base), rel, where)
    return full


def _is_link(path: str) -> bool:
    return os.path.islink(path) or getattr(os.path, "isjunction", lambda p: False)(path)


def _refuse_links(base: str, rel: str, where: str) -> None:
    """Refuse a symbolic link (or Windows junction) anywhere on the way to a bout input or inside it.

    A link is how a file from outside the bout gets hashed, copied into a campaign and shown to judges as if it
    were part of the bout (the independent review did it with /etc/passwd). A hard link cannot be told from a
    file, so the bout directory itself has to be under the organizer's control.
    """
    cur = base
    for part in os.path.normpath(rel).split(os.sep):
        if part in ("", "."):
            continue
        cur = os.path.join(cur, part)
        if _is_link(cur):
            raise Refusal(f"{where}: {rel!r} passes through a symbolic link ({os.path.relpath(cur, base)}); "
                          "links are refused because they can point outside the bout")
    if os.path.isdir(cur):
        for dirpath, dirnames, filenames in os.walk(cur, followlinks=False):
            for name in dirnames + filenames:
                item = os.path.join(dirpath, name)
                if _is_link(item):
                    raise Refusal(f"{where}: {rel!r} contains a symbolic link ({os.path.relpath(item, base)}); "
                                  "links are refused because they can point outside the bout")
                if name in filenames and not os.path.isfile(item):
                    raise Refusal(f"{where}: {rel!r} contains something that is not a regular file "
                                  f"({os.path.relpath(item, base)}); pipes, sockets and devices are refused")
    elif not os.path.isfile(cur):
        raise Refusal(f"{where}: {rel!r} is not a regular file or a directory")


def load_bout(bout_dir: str) -> dict:
    """Load and validate a bout. Adds resolved absolute paths and content hashes.

    Returned extras: '_dir', '_sha256' (of bout.json), candidates[i]['files'][j]['abs'|'sha256'],
    candidates[i]['content_hash'], '_sources' {key: {'path', 'abs', 'sha256'} or a list of those}.
    """
    path = os.path.join(bout_dir, "bout.json")
    _need(os.path.isfile(path), f"no bout.json in {bout_dir}")
    bout = read_json(path)
    where = f"bout {os.path.basename(os.path.abspath(bout_dir))}"
    _need(isinstance(bout, dict), f"{where}: must be a JSON object")
    extra = set(bout) - BOUT_KEYS
    _need(not extra, f"{where}: unknown keys {sorted(extra)}")
    _need(bout.get("schema") == BOUT_SCHEMA, f"{where}: schema must be {BOUT_SCHEMA}")
    _need(ID_RE.match(_str(bout, "bout_id", where)) is not None, f"{where}: bad bout_id")
    for key in ("event", "purpose", "audience"):
        _str(bout, key, where)
    if bout.get("sensitivity") not in SENSITIVITY:
        raise Refusal(f"{where}: sensitivity must be one of {SENSITIVITY}; a bout with no label is not judged")

    cands = bout.get("candidates")
    _need(isinstance(cands, list) and len(cands) >= 1, f"{where}: candidates must be a non-empty list")
    ids = set()
    for c in cands:
        _need(isinstance(c, dict), f"{where}: each candidate must be an object")
        cid = _str(c, "id", where)
        _need(ID_RE.match(cid) is not None and cid not in ids, f"{where}: candidate id '{cid}' invalid or repeated")
        ids.add(cid)
        files = c.get("files")
        _need(isinstance(files, list) and files, f"{where} candidate {cid}: files must be a non-empty list")
        manifest = []
        for f in files:
            _need(isinstance(f, dict), f"{where} candidate {cid}: each file must be an object")
            name = _str(f, "path", f"{where} candidate {cid}")
            _need("/" not in name and "\\" not in name and name not in (".", ".."),
                  f"{where} candidate {cid}: file path must be a plain file name ({name!r})")
            f["abs"] = _resolve(bout_dir, _str(f, "source", f"{where} candidate {cid}"), f"{where} candidate {cid}")
            _need(os.path.isfile(f["abs"]), f"{where} candidate {cid}: {f['source']} is not a file")
            f["sha256"] = sha256_file(f["abs"])
            manifest.append([name, f["sha256"]])
        # The content hash covers file names and bytes. Candidate ids, labels and authors are not part of it.
        from .canon import sha256_obj
        c["content_hash"] = sha256_obj(sorted(manifest))
    baseline = bout.get("baseline")
    if baseline is not None:
        _need(baseline in ids, f"{where}: baseline '{baseline}' is not a candidate id")

    sources = bout.get("sources", {})
    _need(isinstance(sources, dict), f"{where}: sources must be an object")
    resolved: dict[str, Any] = {}
    for key, val in sources.items():
        if isinstance(val, list):
            resolved[key] = []
            for rel in val:
                full = _resolve(bout_dir, rel, f"{where} source {key}")
                resolved[key].append({"path": rel, "abs": full, "sha256": tree_hash(full)})
        else:
            full = _resolve(bout_dir, val, f"{where} source {key}")
            resolved[key] = {"path": val, "abs": full, "sha256": tree_hash(full)}
    _need(isinstance(bout.get("params", {}), dict), f"{where}: params must be an object")

    bout["_dir"] = os.path.abspath(bout_dir)
    bout["_sha256"] = sha256_file(path)
    bout["_sources"] = resolved
    return bout


def bout_overrides(bout: dict, event: dict) -> dict:
    """Check a bout's `params` against what its event card lets a bout change, and return them.

    The event card owns the rules. A bout may set only the parameters the card lists under `bout_may_set` (per
    official, and under format.bracket for the bracket). Anything else is refused: a bout that could point the
    hidden-test official at the visible suite, or empty the forbidden-import list, would decide its own contest.
    What a card does allow is not always harmless: the runnable cards let a bout shrink the judging panel or
    accept a one-family panel, because a real panel has to fit the judges that exist. Every allowed override is
    returned as a flag so it shows in the verdict, and the controller raises its own flags for a thin panel.

    Returns {'officials': {official_id: {param: value}}, 'bracket': {key: value}, 'flags': [...]}.
    """
    where = f"bout {bout.get('bout_id')}"
    params = bout.get("params") or {}
    _need(isinstance(params, dict), f"{where}: params must be an object")
    by_id = {o["id"]: o for o in event.get("officials", [])}
    bracket_fmt = (event.get("format") or {}).get("bracket") or {}
    out = {"officials": {}, "bracket": {}, "flags": []}
    for key in sorted(params):
        val = params[key]
        _need(isinstance(val, dict), f"{where}: params.{key} must be an object")
        if key == "bracket":
            allowed, target = set(bracket_fmt.get("bout_may_set", [])), out["bracket"]
        elif key in by_id:
            allowed, target = set(by_id[key].get("bout_may_set", [])), out["officials"].setdefault(key, {})
        else:
            raise BarclaysError(f"{where}: params names '{key}', which is not an official of event "
                                f"'{event['event_id']}' (officials: {', '.join(sorted(by_id))}) nor 'bracket'")
        refused = sorted(set(val) - allowed)
        if refused:
            raise Refusal(f"{where}: sets {key}.{', '.join(refused)}, which event '{event['event_id']}' does not let "
                          f"a bout change (a bout may set: {', '.join(sorted(allowed)) or 'nothing'}). Decisive "
                          "settings belong to the event card; change the card, which changes its hash.")
        defaults = bracket_fmt if key == "bracket" else (by_id[key].get("params") or {})
        for name in sorted(val):
            value = val[name]
            scalar = (bool, int, float, str)
            ok = isinstance(value, scalar) or (isinstance(value, list) and all(isinstance(v, scalar) for v in value))
            if name in defaults and ok:
                want = defaults[name]
                number = (int, float)
                ok = (isinstance(want, bool) == isinstance(value, bool)) and (
                    type(value) is type(want)
                    or (isinstance(want, number) and isinstance(value, number)))
            if ok and isinstance(value, (int, float)) and not isinstance(value, bool):
                # A number a bout sets must be finite, positive and, where the card has its own value, within a
                # factor of ten of it. A bout that could set a timeout of 1e300 or 0 could break every official
                # and turn any contest INCONCLUSIVE.
                # No card value means nothing to bound the bout's value against, so it is refused: a bout could
                # otherwise set a per-call time limit of 0.01 s and time out every candidate (third review).
                want = defaults.get(name)
                ok = value == value and 0 < value <= 86400 and isinstance(want, (int, float)) and not isinstance(
                    want, bool) and want > 0 and want / 10 <= value <= want * 10
            if not ok:
                raise BarclaysError(f"{where}: params.{key}.{name} has a value the event card does not accept "
                                    f"({value!r}): wrong kind, not finite, not positive, more than ten times "
                                    "away from the card's own value, or a number the card gives no value for")
            target[name] = value
            out["flags"].append(f"BOUT_OVERRIDE:{key}.{name}")
    return out


def check_privacy(component: str, allowed: list, sensitivity: str) -> None:
    """Fail closed: refuse unless the component is cleared for this bout's sensitivity label."""
    if sensitivity not in SENSITIVITY:
        raise Refusal(f"{component}: unknown sensitivity label {sensitivity!r}")
    if sensitivity not in (allowed or []):
        raise Refusal(
            f"{component} is not cleared for '{sensitivity}' material (cleared for: {', '.join(allowed or []) or 'nothing'}). "
            "Clearing it is a decision for the owner of the material, not a setting to flip.")
