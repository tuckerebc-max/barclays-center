"""External officials: evaluators that live in a sibling repository and are called through a file contract.

The core is standard library only. An official that needs a browser, a linter or model weights lives in its own
repository (barclays-officials-web, barclays-officials-game, barclays-officials-code) and is run as a separate
process: the venue writes a request file, the plug-in writes a response file. Nothing is imported. The contract is
docs/PLUGINS.md.

Trust runs one way. The plug-in is venue-installed code named by the venue's plug-in table, never by a bout or a
candidate. What it returns is still validated here: a response that is missing, malformed or out of vocabulary
becomes `unverified`. It never becomes `pass`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time

from .. import SENSITIVITY
from ..canon import canonical, read_json, sha256_bytes, sha256_file, write_json
from ..errors import BarclaysError
from .base import KINDS, REGISTRY, SEVERITIES, STATUSES, Ctx, finding, lead, result

PLUGINS_SCHEMA = "barclays.plugins/0.1"
REQUEST_SCHEMA = "barclays.official-request/0.1"
RESPONSE_SCHEMA = "barclays.official-response/0.1"
VERSION = "0.1.0"
PLUGIN_KEYS = {"argv", "repo", "allowed_sensitivity", "timeout_seconds", "notes"}
_SECRET_WORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL")
_MAX_ITEMS = 500
MAX_RESPONSE_BYTES = 2 * 1024 * 1024      # a response file larger than this is refused unread
MAX_BLOCK_BYTES = 64 * 1024               # metrics and the plug-in's receipt, each, as canonical JSON
MAX_EVIDENCE_BYTES = 4 * 1024             # one finding's evidence

_cache: dict = {}


def load_plugins(path: str | None) -> dict:
    """The venue's plug-in table, or an empty one. Refuses a table that shadows a built-in official."""
    if not path:
        return {"path": None, "sha256": None, "officials": {}}
    path = os.path.abspath(path)
    doc = read_json(path)
    where = f"plug-in table {path}"
    if not isinstance(doc, dict) or doc.get("schema") != PLUGINS_SCHEMA or not isinstance(doc.get("officials"), dict):
        raise BarclaysError(f"{where}: must be an object with schema {PLUGINS_SCHEMA} and an 'officials' object")
    for name, spec in doc["officials"].items():
        if name in REGISTRY:
            raise BarclaysError(f"{where}: '{name}' is a built-in official and cannot be replaced by a plug-in")
        if not isinstance(spec, dict) or set(spec) - PLUGIN_KEYS:
            raise BarclaysError(f"{where}: '{name}' has unknown keys {sorted(set(spec) - PLUGIN_KEYS)}")
        argv = spec.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
            raise BarclaysError(f"{where}: '{name}'.argv must be a non-empty list of strings")
        for arg in argv:
            # A plug-in runs from a scratch folder, so a relative path would mean "whatever is there". Say where.
            if ("/" in arg or "\\" in arg) and not os.path.isabs(arg):
                raise BarclaysError(f"{where}: '{name}'.argv has a relative path ({arg!r}); give absolute paths")
        allowed = spec.get("allowed_sensitivity")
        if not isinstance(allowed, list) or not allowed or any(a not in SENSITIVITY for a in allowed):
            raise BarclaysError(f"{where}: '{name}'.allowed_sensitivity must be drawn from {SENSITIVITY}")
        t = spec.get("timeout_seconds", 120)
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not 0 < t <= 3600:
            raise BarclaysError(f"{where}: '{name}'.timeout_seconds must be a number between 0 and 3600")
    return {"path": path, "sha256": sha256_file(path), "officials": doc["officials"]}


def active_plugins() -> dict:
    """The table named by BARCLAYS_PLUGINS (set by `bc --plugins`), loaded once per path and content."""
    path = os.environ.get("BARCLAYS_PLUGINS") or None
    key = (path, sha256_file(path) if path and os.path.isfile(path) else None)
    if key not in _cache:
        _cache.clear()
        _cache[key] = load_plugins(path)
    return _cache[key]


def child_env() -> dict:
    """The plug-in's environment: the venue's, without anything that looks like a credential and without the
    venue's own settings.

    A plug-in is trusted code, and it still has no business seeing a model route's key, or being told where the
    plug-in table and the controller are (fourth review, R4-02: a plug-in rewrote the table it was listed in).
    """
    env = {k: v for k, v in os.environ.items()
           if not any(w in k.upper() for w in _SECRET_WORDS) and not k.upper().startswith("BARCLAYS_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _text(value, limit: int, problems: list | None = None, what: str = "") -> str:
    """A string field, cut to `limit`. A field that is present and is not a string is a problem, not something to
    stringify: `{'forged': 'obj'}` printed into a report is how a response smuggles shape (R4-03)."""
    if value is None:
        return ""
    if not isinstance(value, str):
        if problems is not None:
            problems.append(f"{what or 'a text field'} must be a string")
        return ""
    return value[:limit]


def _block(value, limit: int, what: str, problems: list) -> dict:
    """An object field kept only if it is an object of a sane size."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        problems.append(f"{what} must be an object")
        return {}
    try:
        size = len(canonical(value))
    except (TypeError, ValueError, RecursionError):
        problems.append(f"{what} is not plain JSON")
        return {}
    if size > limit:
        problems.append(f"{what} is {size} bytes; the limit is {limit}")
        return {}
    return value


def _items(raw, kind: str, problems: list) -> list:
    """Validated findings or leads. Anything malformed is a problem; the caller then refuses the response."""
    out = []
    if raw is None:
        return out
    if not isinstance(raw, list) or len(raw) > _MAX_ITEMS:
        problems.append(f"{kind} must be a list of at most {_MAX_ITEMS} entries")
        return out
    for entry in raw:
        if (not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]
                or not isinstance(entry.get("severity"), str) or entry["severity"] not in SEVERITIES):
            problems.append(f"a {kind[:-1]} needs a string id and a severity from {SEVERITIES}")
            continue
        where = f"{kind[:-1]} {entry['id'][:40]!r}"
        if kind == "findings":
            out.append(finding(entry["id"][:120], entry["severity"],
                               _text(entry.get("claim"), 600, problems, where + " claim"),
                               _text(entry.get("locator"), 240, problems, where + " locator"),
                               _block(entry.get("evidence"), MAX_EVIDENCE_BYTES, where + " evidence", problems)))
        else:
            out.append(lead(entry["id"][:120], _text(entry.get("note"), 600, problems, where + " note"),
                            _text(entry.get("locator"), 240, problems, where + " locator"), entry["severity"]))
    return out


def missing(name: str, has_table: bool = False):
    """An official the event card names and this venue has no plug-in for: not a crash, and not a pass."""
    why = (f"the venue's plug-in table has no entry for '{name}', so this check did not run" if has_table else
           f"no plug-in table was given (--plugins), so '{name}' did not run")

    def run(ctx: Ctx) -> dict:
        return result(ctx, name, "not installed", "deterministic", "unverified", why,
                      receipt={"plugin": name, "plugin_missing": True}, started=time.time())
    return run


def external(name: str, spec: dict):
    """Wrap one plug-in table entry as an official."""
    def run(ctx: Ctx) -> dict:
        started = time.time()
        # Outside the run directory: a plug-in is handed a scratch folder of its own, never a path inside the
        # record it is contributing to (R4-04).
        work = tempfile.mkdtemp(prefix="barclays-ext-")
        argv = list(spec["argv"])
        entry = next((a for a in argv if os.path.isfile(a)), None)
        receipt = {"plugin": name, "repo": spec.get("repo"), "argv": argv,
                   "entry_sha256": sha256_file(entry) if entry else None, "contract": REQUEST_SCHEMA,
                   "wrapper_version": VERSION}

        def unverified(why: str) -> dict:
            shutil.rmtree(work, ignore_errors=True)
            return result(ctx, name, "?", "executable", "unverified", why, receipt=receipt, started=started)

        try:
            request_path = os.path.join(work, "request.json")
            response_path = os.path.join(work, "response.json")
            sources = {}
            for key, value in ctx.bout["_sources"].items():
                sources[key] = ({"abs": value["abs"], "sha256": value["sha256"]} if isinstance(value, dict)
                                else [{"abs": v["abs"], "sha256": v["sha256"]} for v in value])
            write_json(request_path, {
                "schema": REQUEST_SCHEMA, "official_id": ctx.cfg["id"], "official": name,
                "authority": ctx.cfg["authority"],
                "candidate": {"id": ctx.candidate["id"], "content_hash": ctx.candidate["content_hash"],
                              "is_baseline": ctx.is_baseline,
                              "files": [{"path": f["path"], "abs": f["abs"], "sha256": f["sha256"]}
                                        for f in ctx.candidate["files"]]},
                "sources": sources, "params": ctx.params, "sensitivity": ctx.bout["sensitivity"],
                "workdir": work, "response_path": response_path})
            budget = float(spec.get("timeout_seconds", 120))
            t0 = time.time()
            try:
                proc = subprocess.run(argv + [request_path], capture_output=True, timeout=budget, cwd=work,
                                      env=child_env(), stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                receipt.update({"timed_out": True, "budget_seconds": budget})
                return unverified(f"the plug-in did not answer within {budget:g} s")
            except OSError as exc:
                return unverified(f"the plug-in could not be started: {type(exc).__name__}")
            receipt.update({"exit_code": proc.returncode, "wall_seconds": round(time.time() - t0, 3),
                            "stderr_sha256": sha256_bytes(proc.stderr), "stderr_bytes": len(proc.stderr),
                            "stdout_bytes": len(proc.stdout)})
            if proc.returncode != 0:
                return unverified(f"the plug-in exited with code {proc.returncode}")
            try:
                if os.path.islink(response_path) or not os.path.isfile(response_path):
                    return unverified("the plug-in wrote no response file (or left a link in its place)")
                size = os.path.getsize(response_path)
                receipt["response_bytes"] = size
                if size > MAX_RESPONSE_BYTES:
                    return unverified(f"the plug-in's response is {size} bytes; the limit is {MAX_RESPONSE_BYTES}")
                resp = read_json(response_path)
            except (OSError, ValueError, RecursionError):
                return unverified("the plug-in wrote no readable response")
            problems = []
            if not isinstance(resp, dict) or resp.get("schema") != RESPONSE_SCHEMA:
                return unverified(f"the plug-in's response is not a {RESPONSE_SCHEMA} object")
            if resp.get("official") != name:
                problems.append("the response names a different official")
            if resp.get("status") not in STATUSES:
                problems.append(f"status must be one of {STATUSES}")
            if resp.get("kind") not in KINDS:
                problems.append(f"kind must be one of {KINDS}")
            findings = _items(resp.get("findings"), "findings", problems)
            leads = _items(resp.get("leads"), "leads", problems)
            if resp.get("status") == "fail" and not findings:
                problems.append("a fail needs at least one finding")
            if resp.get("status") in ("pass", "not_applicable") and (findings or resp.get("findings")):
                # A finding is an objective defect. "Passed, with a critical defect" is not an answer the venue
                # can act on, so it is refused, not read generously (R4-01). Heuristics belong in leads.
                problems.append(f"a {resp.get('status')} may carry leads but no findings")
            version = _text(resp.get("official_version"), 40, problems, "official_version")
            summary = _text(resp.get("summary"), 300, problems, "summary")
            metrics = _block(resp.get("metrics"), MAX_BLOCK_BYTES, "metrics", problems)
            plugin_receipt = _block(resp.get("receipt"), MAX_BLOCK_BYTES, "receipt", problems)
            if problems:
                receipt["response_problems"] = problems[:8]
                return unverified("the plug-in's response was refused: " + "; ".join(problems[:3]))
            receipt["plugin_receipt"] = plugin_receipt
            receipt["response_sha256"] = sha256_file(response_path)
            out = result(ctx, name, version or "?", resp["kind"], resp["status"], summary, findings=findings,
                         leads=leads, metrics=metrics, receipt=receipt, started=started)
            shutil.rmtree(work, ignore_errors=True)
            return out
        except Exception:
            shutil.rmtree(work, ignore_errors=True)
            raise
    return run


def resolve(name: str, plugins: dict | None = None):
    """(callable, cleared sensitivity labels, origin) for an official name: built-in, plug-in or missing."""
    table = plugins if plugins is not None else active_plugins()
    if name in REGISTRY:
        return REGISTRY[name], list(SENSITIVITY), "built-in"
    spec = table["officials"].get(name)
    if spec is not None:
        return external(name, spec), list(spec["allowed_sensitivity"]), "plug-in"
    return missing(name, bool(table.get("path"))), list(SENSITIVITY), "missing"
