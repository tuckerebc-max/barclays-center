"""The run ledger: a hash-chained event log over content-addressed objects.

Every input, official result, packet, panel record, controller decision and verdict is stored once under
`objects/<sha256>` and referenced from an append-only `ledger.jsonl`. Each event carries the hash of the previous
event, so removing, reordering or editing an event breaks the chain.

What this gives: a reviewer can recompute every hash and see that the verdict was built from exactly these inputs.
`audit` goes further than the chain: the files a reader actually opens (verdict.json, REPORT.md, manifest.json, the
controller's decision, panel packets and results) must still match what the ledger recorded, a finished run must end
in a seal, and the recorded eligibility must be what the recorded official results imply.

What it does not give: authenticity. The chain is an unkeyed hash chain. Anyone who can write to the run directory
can change official results, the weigh-in, the controller's decision, the verdict and the report, recompute every
hash and rebuild the seal, and produce a run that is fully consistent and recommends a candidate the real run
disqualified. The second independent review did exactly that with a 37-line script. Re-deriving eligibility does
not stop it, because the results it is derived from are rewritten too. Or a finished run can be cut back to an
earlier honest-looking state.

So `audit` reports two things and keeps them apart: `consistent` (the directory agrees with itself, which catches
careless edits and nothing more) and `authenticated` (the chain head equals one recorded OUTSIDE the run: a commit
message, a Linear comment). Only the second says this is the run that happened. Without `--expect-head`,
`authenticated` is null and the result line says so.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from . import LEDGER_SCHEMA
from .canon import canonical, read_json, sha256_bytes, sha256_file
from .errors import BarclaysError

GENESIS = "0" * 64


def now() -> str:
    fixed = os.environ.get("BARCLAYS_FIXED_TIME")
    return fixed or datetime.now(timezone.utc).isoformat(timespec="seconds")


class Ledger:
    def __init__(self, run_dir: str):
        self.run_dir = os.path.abspath(run_dir)
        self.objects = os.path.join(self.run_dir, "objects")
        self.path = os.path.join(self.run_dir, "ledger.jsonl")
        os.makedirs(self.objects, exist_ok=True)
        self.seq = 0
        self.head = GENESIS
        if os.path.isfile(self.path):
            ok, problems, head, count = verify(self.run_dir)
            if not ok:
                raise BarclaysError("existing ledger does not verify: " + "; ".join(problems[:3]))
            self.seq, self.head = count, head

    def put_bytes(self, data: bytes) -> str:
        sha = sha256_bytes(data)
        target = os.path.join(self.objects, sha)
        if not os.path.exists(target):
            with open(target, "wb") as fh:
                fh.write(data)
        return sha

    def put_json(self, obj) -> str:
        return self.put_bytes(json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n")

    def put_file(self, path: str) -> str:
        with open(path, "rb") as fh:
            return self.put_bytes(fh.read())

    def append(self, kind: str, summary: dict, refs: dict | None = None) -> dict:
        event = {"schema": LEDGER_SCHEMA, "seq": self.seq + 1, "ts": now(), "kind": kind, "summary": summary,
                 "refs": refs or {}, "prev": self.head}
        event["hash"] = sha256_bytes(canonical(event))
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
        self.seq, self.head = event["seq"], event["hash"]
        return event


def verify(run_dir: str):
    """Recompute the chain and every referenced object. Returns (ok, problems, head, event count)."""
    path = os.path.join(run_dir, "ledger.jsonl")
    objects = os.path.join(run_dir, "objects")
    problems = []
    if not os.path.isfile(path):
        return False, ["no ledger.jsonl"], GENESIS, 0
    prev = GENESIS
    count = 0
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError:
                problems.append(f"line {lineno}: not JSON")
                break
            claimed = event.pop("hash", None)
            if event.get("prev") != prev:
                problems.append(f"event {event.get('seq')}: previous-hash mismatch (chain broken)")
            if event.get("seq") != count + 1:
                problems.append(f"event at line {lineno}: sequence {event.get('seq')} out of order")
            actual = sha256_bytes(canonical(event))
            if actual != claimed:
                problems.append(f"event {event.get('seq')}: content does not match its hash")
            for name, sha in (event.get("refs") or {}).items():
                target = os.path.join(objects, str(sha))
                if not os.path.isfile(target):
                    problems.append(f"event {event.get('seq')}: object for '{name}' is missing")
                elif sha256_file(target) != sha:
                    problems.append(f"event {event.get('seq')}: object for '{name}' has been altered")
            prev = claimed or actual
            count += 1
    return not problems, problems, prev, count


TREE_FORMAT = 2     # 1: files only, databases by rows (0.2.0). 2: adds directories, links and the database schema.


def sqlite_content_hash(path: str, schema: bool = True) -> str:
    """A hash of what a SQLite database SAYS: its schema, every table, every row, sorted. Not of its bytes.

    The controller keeps its ballots and records in SQLite. Opening such a file, even to read it, can move pages
    between the database and its write-ahead log, so its bytes are not stable; its contents are. Hashing the
    contents means a reader can open the database without breaking the seal, and emptying a table breaks it.
    Falls back to the bytes if the file cannot be read as a database.
    """
    import sqlite3
    for uri in (f"file:{path}?mode=ro", f"file:{path}?immutable=1"):
        try:
            con = sqlite3.connect(uri, uri=True, timeout=5)
            try:
                # The schema is part of what a database says: a view, trigger or index added later changes it.
                digest = []
                if schema:
                    rows = sorted(repr(row) for row in con.execute(
                        "select type, name, tbl_name, sql from sqlite_master"))
                    digest.append(["schema", len(rows), sha256_bytes("\n".join(rows).encode("utf-8", "replace"))])
                names = [r[0] for r in con.execute(
                    "select name from sqlite_master where type='table' order by name")]
                for name in names:
                    quoted = '"' + name.replace('"', '""') + '"'
                    rows = sorted(repr(row) for row in con.execute(f"select * from {quoted}"))
                    digest.append([name, len(rows), sha256_bytes("\n".join(rows).encode("utf-8", "replace"))])
                return "sqlite-content:" + sha256_bytes(canonical(digest))
            finally:
                con.close()
        except Exception:  # noqa: BLE001  not a readable database: fall through to the next way, then to bytes
            continue
    return sha256_file(path)


def run_tree(run_dir: str, fmt: int = TREE_FORMAT) -> dict:
    """{relative path: hash} for every file in a run directory, as a seal records it.

    `fmt` is the seal's tree format. A run sealed by version 0.2.0 recorded format 1 (files only, databases by
    their rows); it is still checked by the rules it was sealed under, so an older sealed run keeps verifying.

    Left out, and nothing else: the ledger itself (the seal is in it), bytecode, and SQLite's own side files
    (`x.sqlite-wal`, `x.sqlite-shm`, `x.sqlite-journal`, and only when `x.sqlite` is in the same directory), which
    exist only while a database is open. A SQLite database is hashed by its contents (sqlite_content_hash). Every
    other file is hashed by its bytes, whatever its name.
    """
    out = {}
    for root, dirs, files in os.walk(run_dir, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in (dirs if fmt >= 2 else []):   # directories and links are entries too: adding one is a change
            full = os.path.join(root, name)
            rel = os.path.relpath(full, run_dir).replace(os.sep, "/") + "/"
            out[rel] = "link:" + os.readlink(full) if os.path.islink(full) else "dir"
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, run_dir).replace(os.sep, "/")
            if rel == "ledger.jsonl" or name.endswith(".pyc"):
                continue
            if fmt >= 2 and os.path.islink(full):
                out[rel] = "link:" + os.readlink(full)
                continue
            if fmt >= 2 and not os.path.isfile(full):
                out[rel] = "special"
                continue
            side = next((x for x in ("-wal", "-shm", "-journal") if name.endswith(".sqlite" + x)), None)
            if side and name[:-len(side)] in files:
                continue        # a side file of a database that sits beside it; any other name is hashed
            out[rel] = sqlite_content_hash(full, schema=fmt >= 2) if name.endswith(".sqlite") else sha256_file(full)
    return out


def _events(run_dir: str) -> list:
    out = []
    try:
        with open(os.path.join(run_dir, "ledger.jsonl"), "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        break
    except OSError:
        pass
    return out


def audit(run_dir: str, expect_head: str | None = None) -> dict:
    """Everything `bc verify` checks. Returns {'result', 'consistent', 'authenticated', 'ok', 'head', 'events',
    'sealed', 'problems', 'warnings'}. `ok` is True when no check failed; it is NOT a statement that the run is
    genuine unless `authenticated` is True.

    1. The chain and every referenced object (verify).
    2. Working files against the ledger: the files a reader opens must be the bytes the ledger recorded.
    3. The seal: a run that has a verdict must end with a seal event that still matches the files.
    4. Internal consistency: result events match their objects; eligibility is re-derived from the official
       results; the verdict agrees with the weigh-in, the manifest and the controller's decision.
    5. Optionally, the head against one recorded outside the run. Without that, a consistent rewrite of the whole
       directory, or a run cut back to an earlier state with its later files removed, cannot be detected.
    """
    ok, problems, head, count = verify(run_dir)
    warnings: list = []
    # Permissions and timestamps are outside the seal on purpose: they do not survive a copy, a clone or an
    # archive, so sealing them would fail every run that was moved. A ledger other accounts can write is still
    # worth saying out loud (third review, R3-05).
    try:
        if os.name == "posix" and os.stat(os.path.join(run_dir, "ledger.jsonl")).st_mode & 0o022:
            warnings.append("ledger.jsonl is writable by other accounts on this machine (group or world write bit "
                            "set); permissions are not part of the seal")
    except OSError:
        pass
    events = _events(run_dir)
    last: dict = {}
    for event in events:
        last[event.get("kind")] = event

    def obj(sha):
        return os.path.join(run_dir, "objects", str(sha))

    def load(sha):
        try:
            return read_json(obj(sha))
        except (OSError, ValueError):
            return None

    def state(rel: str, sha: str, as_json: bool) -> str:
        path = os.path.join(run_dir, rel)
        if not os.path.isfile(path):
            return "missing"
        if sha256_file(path) == sha:
            return "ok"
        if as_json:
            try:
                return "ok" if read_json(path) == read_json(obj(sha)) else "altered"
            except (OSError, ValueError):
                return "altered"
        return "altered"

    # 2. working files
    for kind, ref, rel, as_json in (("manifest", "manifest", "manifest.json", True),
                                    ("verdict", "verdict", "verdict.json", True),
                                    ("verdict", "report", "REPORT.md", False),
                                    ("bracket_decision", "decision", "bracket/reports/decision.json", True),
                                    ("shadow_decision", "decision", "shadow-bracket/reports/decision.json", True),
                                    ("panel", "panel", "panel/panel.json", True),
                                    ("panel_attached", "panel", "panel-attached.json", True)):
        event = last.get(kind)
        if event and ref in (event.get("refs") or {}):
            found = state(rel, event["refs"][ref], as_json)
            if found != "ok":
                problems.append(f"{rel} is {found}: it is not what the ledger recorded at event {event.get('seq')}")
    if "verdict" not in last:
        for rel in ("verdict.json", "REPORT.md"):
            if os.path.isfile(os.path.join(run_dir, rel)):
                problems.append(f"{rel} exists but the ledger records no verdict (events may have been removed "
                                "from the end)")
    for event in events:
        if event.get("kind") in ("panel_packet", "panel_result"):
            pid = (event.get("summary") or {}).get("packet_id")
            ref, sub, ext = (("packet", "packets", ".md") if event["kind"] == "panel_packet"
                             else ("result", "results", ".json"))
            found = state(f"panel/{sub}/{pid}{ext}", (event.get("refs") or {}).get(ref), False)
            if found != "ok":
                problems.append(f"panel/{sub}/{pid}{ext} is {found}: it is not what the ledger recorded")

    # 3. the seal
    sealed = bool(events) and events[-1].get("kind") == "seal"
    manifest = load((last.get("manifest", {}).get("refs") or {}).get("manifest")) or {}
    if "verdict" in last:
        if not sealed:
            text = ("the run has a verdict but does not end with a seal (events were added or removed after the "
                    "verdict, or the run was interrupted)")
            (warnings if manifest.get("barclays_version") == "0.1.0" else problems).append(
                text + ("; version 0.1 runs were never sealed" if manifest.get("barclays_version") == "0.1.0" else ""))
        else:
            for rel, sha in ((events[-1].get("summary") or {}).get("files") or {}).items():
                path = os.path.join(run_dir, rel)
                if not os.path.isfile(path) or sha256_file(path) != sha:
                    problems.append(f"{rel} no longer matches the seal")
            tree_sha = (events[-1].get("refs") or {}).get("tree")
            sealed_tree = load(tree_sha) if tree_sha else None
            if isinstance(sealed_tree, dict):
                extra = (events[-1].get("summary") or {}).get("unexpected_entries") or []
                if extra:
                    warnings.append("the sealed run holds entries the venue did not write: "
                                    + ", ".join(str(x) for x in extra[:8]))
                fmt = int((events[-1].get("summary") or {}).get("tree_format", 1))
                if fmt < TREE_FORMAT:
                    warnings.append(f"this run was sealed with tree format {fmt}: added directories, links and "
                                    "database schema objects are not covered by its seal")
                current = run_tree(run_dir, fmt)
                current.pop(f"objects/{tree_sha}", None)
                diffs = ([f"changed: {r}" for r in sorted(sealed_tree) if r in current and current[r] != sealed_tree[r]]
                         + [f"missing: {r}" for r in sorted(sealed_tree) if r not in current]
                         + [f"added: {r}" for r in sorted(current) if r not in sealed_tree])
                if diffs:
                    problems.append(f"the run directory is not what was sealed ({len(diffs)} difference(s)): "
                                    + "; ".join(diffs[:8]))
    elif any(e.get("kind") == "seal" for e in events):
        problems.append("the ledger has a seal but no verdict")
    if any(e.get("kind") == "seal" for e in events[:-1]):
        problems.append("events follow a seal; a sealed run is finished")

    # 4. internal consistency
    for event in events:
        if event.get("kind") == "official_result":
            res = load((event.get("refs") or {}).get("result"))
            summ = event.get("summary") or {}
            if res is None or any(res.get(k) != summ.get(k) for k in ("official_id", "candidate_id", "status")):
                problems.append(f"event {event.get('seq')}: the official result object does not say what its "
                                "ledger entry says")
    weigh = load((last.get("weigh_in", {}).get("refs") or {}).get("weigh_in"))
    if weigh:
        from .weighin import derive_eligibility
        results = [load(sha) for sha in weigh.get("result_objects", [])]
        logged = [(e.get("refs") or {}).get("result") for e in events if e.get("kind") == "official_result"]
        if None in results:
            problems.append("the weigh-in names official results that are missing")
        elif sorted(weigh.get("result_objects", [])) != sorted(logged):
            problems.append("the weigh-in does not cover exactly the official results in the ledger")
        else:
            recorded = weigh.get("eligibility", {})
            baseline = next((cid for cid, e in recorded.items() if e.get("is_baseline")), None)
            derived, _ = derive_eligibility(results, [(cid, e.get("content_hash")) for cid, e in recorded.items()],
                                            baseline)
            for cid in recorded:
                if derived[cid]["status"] != recorded[cid].get("status"):
                    problems.append(f"recorded eligibility of '{cid}' ({recorded[cid].get('status')}) is not what "
                                    f"the official results imply ({derived[cid]['status']})")
        verdict = load((last.get("verdict", {}).get("refs") or {}).get("verdict"))
        if verdict:
            status = {cid: e.get("status") for cid, e in (verdict.get("eligibility") or {}).items()}
            if status != {cid: e.get("status") for cid, e in weigh.get("eligibility", {}).items()}:
                problems.append("the verdict's eligibility is not the weigh-in's")
            for cid in list(verdict.get("recommended") or []) + list(verdict.get("shortlist") or []):
                if status.get(cid) != "eligible":
                    problems.append(f"the verdict names '{cid}', which did not pass the weigh-in")
            if manifest and (verdict.get("provenance") or {}).get("candidates") != {
                    c["id"]: c["content_hash"] for c in manifest.get("candidates", [])}:
                problems.append("the verdict's candidate hashes are not the manifest's")
            decision = load((last.get("bracket_decision", {}).get("refs") or {}).get("decision"))
            if decision:
                d = decision.get("decision") or {}
                if d.get("status") != verdict.get("status") or list(d.get("recommended") or []) != list(
                        verdict.get("recommended") or []):
                    problems.append("the verdict does not say what the controller's decision says")

    # 5. the outside anchor
    if expect_head is not None and expect_head != head:
        problems.append(f"the chain head is {head}, not the expected {expect_head}: this is not the run that was "
                        "recorded")
    if expect_head is None:
        warnings.append("no --expect-head given: a consistent rewrite of the whole run directory, or a run cut "
                        "back to an earlier state, cannot be detected without the head recorded outside the run")
    consistent = not [p for p in problems if "not the expected" not in p]
    authenticated = None if expect_head is None else (expect_head == head)
    if not consistent:
        line = "NOT CONSISTENT: the run directory does not agree with its own ledger"
    elif authenticated is None:
        line = ("CONSISTENT, NOT AUTHENTICATED: the directory agrees with itself. Whether it is the run that "
                "happened is unknown without the head recorded outside it (--expect-head)")
    elif authenticated:
        line = "CONSISTENT AND AUTHENTICATED: the chain head is the one recorded outside the run"
    else:
        line = "NOT AUTHENTICATED: the chain head is not the one recorded outside the run"
    return {"result": line, "consistent": consistent, "authenticated": authenticated, "ok": not problems,
            "head": head, "events": count, "sealed": sealed, "problems": problems, "warnings": warnings}
