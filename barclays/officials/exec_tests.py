"""py.exec_tests: run a test suite against a candidate and report what actually happened.

This is the official that keeps "a model says it looks good" from standing in for execution. It runs one named suite
from the bout's sources (visible tests, PASS_TO_PASS regression tests, or hidden FAIL_TO_PASS target tests, the
SWE-bench vocabulary) against the candidate and returns per-test outcomes with a receipt.

Who runs where (version 0.2; version 0.1 ran tests and candidate in one process, and a candidate could forge its
own results, which the independent review demonstrated):

  the ORACLE   a separate process that runs the suite with unittest. It never imports candidate code. Where the
               suite says `from solution import merge_intervals` it gets a generated stand-in whose functions
               forward each call to the worker and wait for the answer.
  the WORKER   a second process that imports the candidate and answers calls. Everything in it is assumed to be
               under the candidate's control. All it can send back is a return value or an exception, as plain
               data (numbers, strings, lists, tuples, sets, dicts, bytes). An object with a rigged `__eq__` cannot
               cross; the oracle rebuilds builtin values, and the suite compares those with ordinary `==`.
  the JAIL     on Linux with unprivileged user namespaces, the worker runs with no network, in its own PID
               namespace, chrooted into a private root that holds the interpreter (read-only) and the candidate's
               files (read-only) and nothing else: not the suite, not the bout, not the run directory, not $HOME.
               Where that is unavailable the worker is a plain child process and the receipt says
               `filesystem: not_isolated`; the verdict carries EXEC_NOT_ISOLATED.

What this is not: a hardened sandbox. A namespace jail shares the host kernel, and resource limits are best
effort. It is sufficient for candidates written by the Navy Yard's own lanes. Code from an untrusted author needs
bubblewrap, nsjail or a disposable VM, and material above 'internal' is refused by the event card.

What crosses the boundary, and so what a suite can test: module-level functions called with plain data, and
module-level constants. A suite that needs candidate classes, callbacks or object identity gets 'unverified' with
the reason; that is a limit of this official, not a failure of the candidate.

Rules:
  - Zero tests collected is 'unverified', never a pass. A skipped test is 'unverified', never a pass.
  - A candidate that will not import, exits, or dies mid-call has failed; the suite ran and the candidate did not
    answer.
  - A candidate call that does not return in time is retried once with twice the budget. Two timeouts are a
    failure of the candidate. A suite that is itself too slow for the budget is 'unverified'. The clock starts
    when the worker is up: the time it takes to build the jail is the harness's, not the candidate's.
  - If the worker never starts, the oracle dies, or its result cannot be read, the status is 'unverified': the
    harness failed, not the candidate.
  - An answer may add at most `max_reply_bytes` (64 KB unless the event card says otherwise) beyond twice the
    size of its own request, so a large input may have a large answer. The limit is what keeps a candidate from
    stalling the oracle with an answer that takes minutes to compare. Arguments are sent back only when the call
    changed them.
  - Two things one official run cannot attribute: a suite that ran out of time while the candidate was not being
    waited on (`unattributed_timeout`), and an answer over the size limit (`unattributed_limit`). Both are
    reported 'unverified', and the weigh-in then looks across candidates (weighin.attribute_limits): a timeout
    that another candidate did not have, or an oversize answer on a suite another candidate PASSED, is a failure
    of this candidate. If nobody else got through, it stays 'unverified' and the reason is printed. A wrong
    candidate that is alone in its bout can therefore still end 'unverified' this way; it cannot end 'pass'.
  - Equality is the suite's: unittest compares with Python's `==`, so `1.0 == 1` and `True == 1`. The oracle
    preserves the JSON type of every value (int, float, bool, str, list, tuple, set, dict); a suite that cares
    about exact types has to assert them.
  - Nothing from the hidden suite is left in the run directory. Candidate output is recorded by hash and size only.
  - `reveal` says how much of a suite a result may show: 'traces' (test names and the tail of each traceback; for
    suites the authors can already see), 'names' (test names only; the default) or 'counts' (how many failed, with
    digests of the test ids; for held-back suites, whose names, inputs and expected values must not reach a report,
    a panel packet or an author).
"""
from __future__ import annotations

import ast
import fnmatch
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

from ..canon import sha256_bytes, tree_hash
from .base import Ctx, finding, register, result

VERSION = "0.2.0"

# ---------------------------------------------------------------------------------------------------------------
# The worker. Runs inside the jail. Candidate code executes here; nothing it does is trusted.
# ---------------------------------------------------------------------------------------------------------------
WORKER = r'''
import importlib, json, os, sys

chan_out = os.fdopen(os.dup(1), "w", encoding="utf-8", buffering=1)
os.dup2(2, 1)                      # anything the candidate prints goes to stderr, never onto the channel
chan_in = sys.stdin
sys.stdin = None
sys.stdout = sys.stderr
cand_dir, token = sys.argv[1], sys.argv[2]
os.chdir(cand_dir)
sys.path.insert(0, cand_dir)


def enc(x, depth=0):
    if depth > 40:
        return {"t": "o", "type": type(x).__name__, "repr": "<nested too deeply>"}
    if x is None or x is True or x is False:
        return x
    if isinstance(x, bool):
        return bool(x)
    if isinstance(x, int):
        return int.__add__(x, 0)
    if isinstance(x, float):
        f = float.__mul__(x, 1.0)
        if f != f or f in (float("inf"), float("-inf")):
            return {"t": "f", "v": repr(f)}
        return f
    if isinstance(x, str):
        return str.__getitem__(x, slice(None))
    if isinstance(x, (bytes, bytearray)):
        return {"t": "b", "v": bytes(x).hex()}
    if isinstance(x, list):
        return [enc(v, depth + 1) for v in list.__iter__(x)]
    if isinstance(x, tuple):
        return {"t": "t", "v": [enc(v, depth + 1) for v in tuple.__iter__(x)]}
    if isinstance(x, (set, frozenset)):
        return {"t": "s" if isinstance(x, set) else "fs", "v": [enc(v, depth + 1) for v in x]}
    if isinstance(x, dict):
        return {"t": "d", "v": [[enc(k, depth + 1), enc(v, depth + 1)] for k, v in dict.items(x)]}
    try:
        text = repr(x)[:200]
    except BaseException:
        text = "<unprintable>"
    return {"t": "o", "type": type(x).__name__, "repr": text}


def dec(x, depth=0):
    if depth > 60:
        raise ValueError("nested too deeply")
    if isinstance(x, list):
        return [dec(v, depth + 1) for v in x]
    if isinstance(x, dict):
        t, v = x.get("t"), x.get("v")
        if t == "t":
            return tuple(dec(i, depth + 1) for i in v)
        if t == "s":
            return set(dec(i, depth + 1) for i in v)
        if t == "fs":
            return frozenset(dec(i, depth + 1) for i in v)
        if t == "d":
            return {dec(k, depth + 1): dec(val, depth + 1) for k, val in v}
        if t == "b":
            return bytes.fromhex(v)
        if t == "f":
            return float(v)
        raise ValueError("unknown tag")
    return x


def send(obj):
    try:
        line = json.dumps(obj)
    except BaseException as exc:
        line = json.dumps({"ok": False, "stage": "encode", "exc": type(exc).__name__, "msg": str(exc)[:200]})
    chan_out.write(line + "\n")
    chan_out.flush()


send({"hello": token})
modules = {}
for raw in chan_in:
    try:
        msg = json.loads(raw)
    except ValueError:
        continue
    name = msg.get("module")
    if name not in modules:
        try:
            modules[name] = importlib.import_module(name)
        except BaseException as exc:
            send({"ok": False, "stage": "import", "exc": type(exc).__name__, "msg": str(exc)[:300]})
            continue
    mod = modules[name]
    attr = msg.get("name")
    if msg.get("op") == "getattr":
        if not hasattr(mod, attr):
            send({"ok": True, "kind": "missing"})
            continue
        obj = getattr(mod, attr)
        if isinstance(obj, type):
            send({"ok": True, "kind": "class"})
        elif callable(obj):
            send({"ok": True, "kind": "callable"})
        else:
            send({"ok": True, "kind": "value", "v": enc(obj)})
        continue
    try:
        args, kwargs = dec(msg.get("a", [])), dec(msg.get("k", {"t": "d", "v": []}))
    except BaseException as exc:
        send({"ok": False, "stage": "decode", "exc": type(exc).__name__, "msg": str(exc)[:200]})
        continue
    before = json.dumps([msg.get("a", []), msg.get("k", {"t": "d", "v": []})], sort_keys=True)

    def changed():
        """The arguments as they are now, only if the call changed them: an honest answer should not have to
        carry its own input back, and the size limit is on what the candidate adds."""
        try:
            now = [enc(args), enc(kwargs)]
            return {} if json.dumps(now, sort_keys=True) == before else {"a": now[0], "k": now[1]}
        except BaseException:
            return {}
    try:
        value = getattr(mod, attr)(*args, **kwargs)
        send(dict({"ok": True, "r": enc(value)}, **changed()))
    except BaseException as exc:
        send(dict({"ok": False, "stage": "call", "exc": type(exc).__name__, "msg": str(exc)[:500]}, **changed()))
'''

# ---------------------------------------------------------------------------------------------------------------
# The oracle. Trusted. Runs the suite; never imports candidate code. Reads its configuration (with the nonce) from
# stdin and writes exactly one result line to a private copy of stdout.
# ---------------------------------------------------------------------------------------------------------------
ORACLE = r'''
import builtins, json, os, queue, signal, subprocess, sys, threading, time, unittest

cfg = json.loads(sys.stdin.readline())
out = os.fdopen(os.dup(1), "w", encoding="utf-8")
os.dup2(2, 1)                      # anything the suite prints goes to stderr, never onto the result channel
sys.stdout = sys.stderr
MAX_REPLY = int(cfg.get("max_reply_bytes", 65536))  # what an answer may add beyond a multiple of its own request.
#                                    Small on purpose: the suite's work on an answer (comparing, printing a diff)
#                                    is time the candidate shapes, and a huge answer is how it would stall the
#                                    oracle. Scaled by the request so a large input may have a large answer.
MAX_LINE = 64 * 1024 * 1024        # hard ceiling on one line read from the worker
MAX_QUEUED = 4                     # unread answers held in memory; beyond this the worker blocks on its pipe
BUILTIN_EXC = {n: getattr(builtins, n) for n in (
    "ValueError", "TypeError", "KeyError", "IndexError", "ZeroDivisionError", "AttributeError", "RuntimeError",
    "NotImplementedError", "OverflowError", "RecursionError", "LookupError", "ArithmeticError", "AssertionError",
    "StopIteration", "UnicodeError", "FloatingPointError", "MemoryError", "OSError", "Exception")}


class CandidateRaised(RuntimeError):
    """The candidate raised something that is not a plain builtin exception."""


class CandidateDead(RuntimeError):
    """The candidate process is gone: it exited, was killed for time, or broke the protocol."""


class HarnessUnsupported(Exception):
    """The suite needs something this official cannot carry across a process boundary."""


class Opaque:
    """What the oracle holds when the candidate returned something that is not plain data. Equal to nothing."""

    def __init__(self, type_name, text):
        self.type_name, self.text = str(type_name)[:80], str(text)[:200]

    def __repr__(self):
        return f"<candidate returned a {self.type_name}: {self.text}>"

    def __eq__(self, other):
        return False

    def __ne__(self, other):
        return True

    __hash__ = None


def enc(x, depth=0):
    if depth > 40:
        raise HarnessUnsupported("argument nested too deeply")
    if x is None or isinstance(x, (bool, int, str)):
        return x
    if isinstance(x, float):
        if x != x or x in (float("inf"), float("-inf")):
            return {"t": "f", "v": repr(x)}
        return x
    if isinstance(x, (bytes, bytearray)):
        return {"t": "b", "v": bytes(x).hex()}
    if isinstance(x, list):
        return [enc(v, depth + 1) for v in x]
    if isinstance(x, tuple):
        return {"t": "t", "v": [enc(v, depth + 1) for v in x]}
    if isinstance(x, (set, frozenset)):
        return {"t": "s" if isinstance(x, set) else "fs", "v": [enc(v, depth + 1) for v in x]}
    if isinstance(x, dict):
        return {"t": "d", "v": [[enc(k, depth + 1), enc(v, depth + 1)] for k, v in x.items()]}
    raise HarnessUnsupported(f"cannot pass a {type(x).__name__} to the candidate")


def dec(x, depth=0):
    if depth > 60:
        raise ValueError("nested too deeply")
    if x is None or isinstance(x, (bool, int, float, str)):
        return x
    if isinstance(x, list):
        return [dec(v, depth + 1) for v in x]
    if isinstance(x, dict):
        t, v = x.get("t"), x.get("v")
        if t == "o":
            client.opaque += 1
            return Opaque(x.get("type"), x.get("repr"))
        if t == "f" and v in ("nan", "inf", "-inf"):
            return float(v)
        if t == "b" and isinstance(v, str):
            return bytes.fromhex(v)
        if isinstance(v, list):
            if t == "t":
                return tuple(dec(i, depth + 1) for i in v)
            if t == "s":
                return set(dec(i, depth + 1) for i in v)
            if t == "fs":
                return frozenset(dec(i, depth + 1) for i in v)
            if t == "d":
                return {dec(k, depth + 1): dec(val, depth + 1) for k, val in v}
    raise ValueError("not a value")


def sync(orig, after):
    """Make the suite's own object show what the candidate did to its copy, so 'does not modify its input' can
    still be tested across the process boundary."""
    if isinstance(orig, list) and isinstance(after, list):
        if len(orig) != len(after):
            orig[:] = after
            return
        for i, (o, a) in enumerate(zip(orig, after)):
            if type(o) is type(a) and isinstance(o, (list, dict, set)):
                sync(o, a)
            elif type(o) is not type(a) or o != a:
                orig[i] = a
    elif isinstance(orig, dict) and isinstance(after, dict):
        for key in [k for k in orig if k not in after]:
            del orig[key]
        for key, a in after.items():
            if key in orig and type(orig[key]) is type(a) and isinstance(a, (list, dict, set)):
                sync(orig[key], a)
            elif key not in orig or type(orig[key]) is not type(a) or orig[key] != a:
                orig[key] = a
    elif isinstance(orig, set) and isinstance(after, set) and orig != after:
        orig.clear()
        orig.update(after)


class Client:
    def __init__(self):
        self.proc = None
        self.q = queue.Queue(maxsize=MAX_QUEUED)   # bounded: a worker that floods the channel cannot eat memory
        self.dead = None            # why the candidate process is gone
        self.harness_error = None   # why the worker never came up
        self.calls = self.timeouts = self.protocol_errors = self.opaque = 0
        self.over_limit = None      # (answer bytes, allowed bytes) when an answer was too long
        self.seconds = 0.0
        self.budget_exhausted = False
        self.import_errors = {}
        self.unsupported = []
        self.deadline = None        # set once the worker is up: starting the jail is harness time, not the
        self.started = None         # candidate's, and must not be charged to its budget

    def start(self):
        pre = None
        if os.name == "posix":
            def pre():
                import resource
                for what, value in cfg["rlimits"]:
                    try:
                        resource.setrlimit(getattr(resource, what), (value, value))
                    except (ValueError, OSError, AttributeError):
                        pass
        try:
            with open(cfg["candidate_stderr"], "wb") as err:
                self.proc = subprocess.Popen(cfg["worker_cmd"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                             stderr=err, cwd=cfg["worker_cwd"], env=cfg["worker_env"],
                                             preexec_fn=pre, start_new_session=(os.name == "posix"))
        except OSError as exc:
            self.harness_error = f"could not start the worker: {exc}"
            return
        threading.Thread(target=self._reader, daemon=True).start()
        hello = self._recv(float(cfg["start_seconds"]))
        if not (isinstance(hello, dict) and hello.get("hello") == cfg["token"]):
            self.harness_error = "the worker did not start (no handshake)"
            self.kill()
            return
        self.started = time.monotonic()
        self.deadline = self.started + float(cfg["budget_seconds"])

    def _reader(self):
        stream = self.proc.stdout
        while True:
            line = stream.readline(MAX_LINE + 1)
            if not line:
                self.q.put(None)
                return
            self.q.put(line)

    def _recv(self, wait, allowed=MAX_LINE):
        try:
            line = self.q.get(timeout=max(0.01, wait))
        except queue.Empty:
            return "timeout"
        if line is None:
            return "eof"
        if len(line) > allowed:
            self.over_limit = [len(line), allowed]
            return "too_long"
        if not line.endswith(b"\n"):
            return "garbage"
        try:
            return json.loads(line.decode("utf-8"))
        except (ValueError, RecursionError, UnicodeDecodeError):
            return "garbage"

    def kill(self):
        if self.proc is None:
            return
        try:
            if os.name == "posix":
                os.killpg(self.proc.pid, signal.SIGKILL)
            else:
                self.proc.kill()
        except (OSError, ProcessLookupError):
            pass

    def ask(self, msg):
        if self.harness_error:
            raise HarnessUnsupported(self.harness_error)
        if self.dead:
            raise CandidateDead(self.dead)
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            self.budget_exhausted = True
            self.dead = "the time budget for this suite ran out"
            self.kill()
            raise CandidateDead(self.dead)
        request = (json.dumps(msg) + "\n").encode("utf-8")
        try:
            self.proc.stdin.write(request)
            self.proc.stdin.flush()
        except (OSError, ValueError):
            self.dead = "the candidate process exited"
            raise CandidateDead(self.dead)
        limit = float(cfg["call_seconds"])
        wait = min(limit, remaining)
        t0 = time.monotonic()
        reply = self._recv(wait, min(MAX_LINE, MAX_REPLY + 2 * len(request)))
        self.seconds += time.monotonic() - t0
        if reply == "timeout":
            if wait >= limit:
                self.timeouts += 1
                self.dead = f"a call did not return within {limit:g} seconds"
            else:
                self.budget_exhausted = True
                self.dead = "the time budget for this suite ran out"
            self.kill()
            raise CandidateDead(self.dead)
        if reply == "eof":
            self.dead = "the candidate process exited"
            raise CandidateDead(self.dead)
        if not isinstance(reply, dict):
            self.protocol_errors += 1
            self.dead = (f"an answer of {self.over_limit[0]} bytes exceeded the {self.over_limit[1]} allowed "
                         "for that call" if reply == "too_long"
                         else "the candidate process sent something that is not an answer")
            self.kill()
            raise CandidateDead(self.dead)
        return reply

    def lookup(self, module, name):
        reply = self.ask({"op": "getattr", "module": module, "name": name})
        if not reply.get("ok"):
            text = f"{reply.get('exc')}: {str(reply.get('msg'))[:200]}"
            self.import_errors[module] = text
            raise ImportError(f"candidate module '{module}' could not be imported ({text})")
        kind = reply.get("kind")
        if kind == "missing":
            raise AttributeError(f"candidate module '{module}' has no attribute '{name}'")
        if kind == "class":
            self.unsupported.append(f"{module}.{name} is a class")
            raise HarnessUnsupported(f"{module}.{name} is a class; this official carries functions and plain data")
        if kind == "value":
            try:
                return dec(reply.get("v"))
            except (ValueError, TypeError, RecursionError):
                self.protocol_errors += 1
                return Opaque("unreadable value", "")

        def stub(*args, **kwargs):
            return self.call(module, name, args, kwargs)
        stub.__name__ = name
        return stub

    def call(self, module, name, args, kwargs):
        try:
            payload = {"op": "call", "module": module, "name": name, "a": enc(list(args)), "k": enc(kwargs)}
        except HarnessUnsupported as exc:
            self.unsupported.append(f"{module}.{name}: {exc}")
            raise
        self.calls += 1
        reply = self.ask(payload)
        try:
            after_args, after_kwargs = dec(reply.get("a", [])), dec(reply.get("k", {"t": "d", "v": []}))
            for o, a in zip(args, after_args if isinstance(after_args, list) else []):
                sync(o, a)
            if isinstance(after_kwargs, dict):
                for key, o in kwargs.items():
                    if key in after_kwargs:
                        sync(o, after_kwargs[key])
            if reply.get("ok"):
                return dec(reply.get("r"))
        except (ValueError, TypeError, RecursionError):
            self.protocol_errors += 1
            return Opaque("unreadable value", "")
        exc, text = str(reply.get("exc")), str(reply.get("msg"))[:500]
        if reply.get("stage") == "call" and exc in BUILTIN_EXC:
            raise BUILTIN_EXC[exc](text)
        raise CandidateRaised(f"{exc}: {text}")


client = Client()
_stubs = {}


def module_proxy(module):
    def __getattr__(name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        key = (module, name)
        if key not in _stubs:
            value = client.lookup(module, name)
            if not callable(value):
                return value
            _stubs[key] = value
        return _stubs[key]
    return __getattr__


class Recorder(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.outcomes = {}

    def addSuccess(self, test):
        self.outcomes[test.id()] = "pass"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes[test.id()] = "fail"

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes[test.id()] = "error"

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes[test.id()] = "skip"

    def addExpectedFailure(self, test, err):
        self.outcomes[test.id()] = "fail"

    def addUnexpectedSuccess(self, test):
        self.outcomes[test.id()] = "fail"


report = {"nonce": cfg["nonce"], "tests_run": 0, "outcomes": {}, "detail": [], "seconds": 0.0}
m0 = time.monotonic()
try:
    client.start()
    if not client.harness_error:
        sys.path.append(cfg["proxy_dir"])      # after the standard library: a candidate file named like a
        sys.path.insert(0, cfg["suite_dir"])   # stdlib module must never stand in for it inside the oracle
        suite = unittest.defaultTestLoader.discover(cfg["suite_dir"], pattern="test_*.py",
                                                    top_level_dir=cfg["suite_dir"])
        rec = Recorder()
        suite.run(rec)
        report.update(tests_run=rec.testsRun, outcomes=rec.outcomes,
                      detail=[{"test": t.id(), "trace": tb[-400:]} for t, tb in (rec.failures + rec.errors)][:25])
finally:
    client.kill()
    report["seconds"] = round(time.monotonic() - client.started, 3) if client.started else 0.0
    report["startup_seconds"] = round((client.started or time.monotonic()) - m0, 3)
    report["harness_error"] = client.harness_error
    report["candidate"] = {"calls": client.calls, "seconds": round(client.seconds, 3), "timeouts": client.timeouts,
                           "budget_exhausted": client.budget_exhausted, "dead": client.dead,
                           "import_errors": client.import_errors, "unsupported": client.unsupported[:10],
                           "protocol_errors": client.protocol_errors, "opaque_returns": client.opaque,
                           "over_limit": client.over_limit}
    out.write("BCRESULT " + json.dumps(report) + "\n")
    out.flush()
'''

# ---------------------------------------------------------------------------------------------------------------
# The jail. Runs as root of a fresh user namespace with its own mount, PID and network namespaces.
# ---------------------------------------------------------------------------------------------------------------
JAIL = r'''set -e
R="$1"; CAND="$2"; BIN="$3"; N="$4"; shift 4
mount -t tmpfs -o size=64m,mode=755 tmpfs "$R"
i=0
while [ "$i" -lt "$N" ]; do
  d="$1"; shift; i=$((i+1))
  if [ -d "$d" ]; then
    mkdir -p "$R$d"; mount --rbind "$d" "$R$d"; mount -o remount,bind,ro "$R$d" 2>/dev/null || true
  fi
done
mkdir -p "$R/etc"
for f in /etc/ld.so.cache /etc/ld.so.conf; do
  if [ -e "$f" ]; then : > "$R$f"; mount --bind "$f" "$R$f"; fi
done
if [ -d /etc/ld.so.conf.d ]; then mkdir -p "$R/etc/ld.so.conf.d"; mount --rbind /etc/ld.so.conf.d "$R/etc/ld.so.conf.d"; fi
mkdir -p "$R/cand" "$R/jailbin" "$R/tmp"
mount --bind "$CAND" "$R/cand"; mount -o remount,bind,ro "$R/cand" 2>/dev/null || true
mount --bind "$BIN" "$R/jailbin"; mount -o remount,bind,ro "$R/jailbin" 2>/dev/null || true
PY="$1"; shift
cd /
exec chroot "$R" "$PY" -I -S -B "$@"
'''

HARNESS_SHA256 = sha256_bytes((WORKER + ORACLE + JAIL).encode("utf-8"))
_SYSTEM_BINDS = ("/usr", "/lib", "/lib64", "/lib32", "/bin", "/sbin")
_JAIL_CACHE: dict = {}
_NETNS = None


def _binds_for(python: str) -> list:
    """Directories the interpreter needs inside the jail: the system ones, plus its own prefix if it lives
    elsewhere (a pyenv or a relocated build)."""
    binds = list(_SYSTEM_BINDS)
    extra = {os.path.dirname(os.path.dirname(python))}
    if os.path.realpath(sys.executable) == python:
        extra.update({os.path.realpath(sys.base_prefix), os.path.realpath(sys.base_exec_prefix)})
    for d in sorted(extra):
        if d and d != "/" and not any(d == b or d.startswith(b + "/") for b in binds):
            binds.append(d)
    return binds


def _jail_prefix(python: str, kill_child: bool, jail_sh: str, root: str, cand: str, bindir: str) -> list:
    binds = _binds_for(python)
    return (["unshare", "-r", "-n", "-m", "-p", "-f"] + (["--kill-child=KILL"] if kill_child else [])
            + ["sh", jail_sh, root, cand, bindir, str(len(binds))] + binds + [python])


def _jail_mode(python: str) -> str:
    """'jail+kill', 'jail' or '' for this interpreter. Probed once by running a trivial program in the jail."""
    if python in _JAIL_CACHE:
        return _JAIL_CACHE[python]
    mode = ""
    if sys.platform.startswith("linux") and shutil.which("unshare") and shutil.which("chroot"):
        probe = tempfile.mkdtemp(prefix="bc-jailprobe-")
        try:
            for sub in ("root", "cand", "bin"):
                os.mkdir(os.path.join(probe, sub))
            jail_sh = os.path.join(probe, "jail.sh")
            with open(jail_sh, "w", encoding="utf-8") as fh:
                fh.write(JAIL)
            for candidate_mode, kill in (("jail+kill", True), ("jail", False)):
                cmd = _jail_prefix(python, kill, jail_sh, os.path.join(probe, "root"), os.path.join(probe, "cand"),
                                   os.path.join(probe, "bin")) + ["-c", "print(6*7)"]
                try:
                    proc = subprocess.run(cmd, capture_output=True, timeout=20, env=_env())
                except (OSError, subprocess.SubprocessError):
                    continue
                if proc.returncode == 0 and proc.stdout.strip() == b"42":
                    mode = candidate_mode
                    break
        finally:
            shutil.rmtree(probe, ignore_errors=True)
    _JAIL_CACHE[python] = mode
    return mode


def _netns_available() -> bool:
    global _NETNS
    if _NETNS is None:
        ok = False
        if sys.platform.startswith("linux") and shutil.which("unshare"):
            try:
                ok = subprocess.run(["unshare", "-rn", "true"], capture_output=True, timeout=10).returncode == 0
            except (OSError, subprocess.SubprocessError):
                ok = False
        _NETNS = ok
    return _NETNS


def _env() -> dict:
    env = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0",
           "LANG": "C.UTF-8"}
    if os.name == "nt":
        env["PATH"] = os.environ.get("PATH", "")
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
    return env


def expected_test_ids(suite_dir: str) -> set:
    """Test ids the suite's own source declares, read without running anything. Used to notice dropped tests."""
    ids = set()
    for name in sorted(os.listdir(suite_dir)):
        if not fnmatch.fnmatch(name, "test_*.py"):
            continue
        try:
            with open(os.path.join(suite_dir, name), "r", encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
        except (OSError, SyntaxError, ValueError):
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [b.attr if isinstance(b, ast.Attribute) else getattr(b, "id", "") for b in node.bases]
            if "TestCase" not in bases:
                continue
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test"):
                    ids.add(f"{name[:-3]}.{node.name}.{item.name}")
    return ids


def _attempt(ctx: Ctx, work: str, suite_dir: str, python: str, budget: float, call_seconds: float) -> dict:
    """One run of the suite. Returns {'data': report or None, 'receipt': {...}}."""
    host, cand, bindir, root = (os.path.join(work, d) for d in ("host", "cand", "bin", "root"))
    for d in (host, cand, bindir, root):
        os.makedirs(d, exist_ok=True)
    modules = []
    for f in ctx.candidate["files"]:
        dest = os.path.join(cand, f["path"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(f["abs"], dest)
        if os.sep not in f["path"] and "/" not in f["path"] and f["path"].endswith(".py"):
            modules.append(f["path"][:-3])
    proxy_dir = os.path.join(host, "proxies")
    os.makedirs(proxy_dir, exist_ok=True)
    for mod in modules:
        with open(os.path.join(proxy_dir, mod + ".py"), "w", encoding="utf-8") as fh:
            fh.write(f"import __main__ as _oracle\n__getattr__ = _oracle.module_proxy({mod!r})\n")
    for name, body, where in (("worker.py", WORKER, bindir), ("oracle.py", ORACLE, host), ("jail.sh", JAIL, host)):
        with open(os.path.join(where, name), "w", encoding="utf-8") as fh:
            fh.write(body)

    token, nonce = secrets.token_hex(8), secrets.token_hex(16)
    mode = _jail_mode(python) if ctx.params.get("deny_network", True) else ""
    if mode:
        worker_cmd = _jail_prefix(python, mode == "jail+kill", os.path.join(host, "jail.sh"), root, cand, bindir) \
            + ["/jailbin/worker.py", "/cand", token]
        network, filesystem = "denied (network namespace)", \
            "isolated (chroot in a private mount namespace: interpreter and candidate files only, read-only)"
    else:
        worker_cmd = [python, "-I", "-S", "-B", os.path.join(bindir, "worker.py"), cand, token]
        network, filesystem = "not_enforced", "not_isolated"
        if ctx.params.get("deny_network", True) and _netns_available():
            worker_cmd = ["unshare", "-rn", "--"] + worker_cmd
            network = "denied (network namespace)"
    stderr_path = os.path.join(host, "candidate.stderr")
    cfg = {"nonce": nonce, "token": token, "suite_dir": suite_dir, "proxy_dir": proxy_dir, "worker_cmd": worker_cmd,
           "worker_cwd": cand, "worker_env": _env(), "candidate_stderr": stderr_path, "budget_seconds": budget,
           "call_seconds": call_seconds, "start_seconds": 20,
           "max_reply_bytes": int(ctx.params.get("max_reply_bytes", 65536)),
           "rlimits": [["RLIMIT_CPU", int(budget) + 10], ["RLIMIT_FSIZE", 32 * 1024 * 1024], ["RLIMIT_CORE", 0],
                       ["RLIMIT_AS", 2 * 1024 * 1024 * 1024]]}
    hard = budget + 30
    oracle_timed_out = False
    t0 = time.time()
    try:
        proc = subprocess.run([python, "-I", "-S", "-B", os.path.join(host, "oracle.py")], cwd=host, env=_env(),
                              input=(json.dumps(cfg) + "\n").encode("utf-8"), capture_output=True, timeout=hard)
        exit_code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        oracle_timed_out = True
        exit_code, stdout, stderr = None, exc.stdout or b"", exc.stderr or b""
    wall = round(time.time() - t0, 3)

    data = None
    for line in stdout.decode("utf-8", errors="replace").splitlines():
        if line.startswith("BCRESULT "):
            try:
                parsed = json.loads(line[len("BCRESULT "):])
            except ValueError:
                continue
            if isinstance(parsed, dict) and parsed.get("nonce") == nonce and isinstance(parsed.get("outcomes"), dict):
                data = parsed
    cand_err = b""
    try:
        with open(stderr_path, "rb") as fh:
            cand_err = fh.read()
    except OSError:
        pass
    receipt = {"exit_code": exit_code, "oracle_timed_out": oracle_timed_out, "wall_seconds": wall,
               "budget_seconds": budget, "call_timeout_seconds": call_seconds, "network": network,
               "filesystem": filesystem, "kill_on_exit": mode == "jail+kill",
               "result_authenticated": data is not None,
               "oracle_stdout_sha256": sha256_bytes(stdout), "oracle_stderr_sha256": sha256_bytes(stderr),
               "candidate_stderr_sha256": sha256_bytes(cand_err), "candidate_stderr_bytes": len(cand_err)}
    if data is None:
        receipt["oracle_stderr_tail"] = stderr.decode("utf-8", errors="replace")[-300:]
    return {"data": data, "receipt": receipt}


@register("py.exec_tests")
def exec_tests(ctx: Ctx) -> dict:
    started = time.time()
    name = "py.exec_tests"
    suite_key = ctx.params.get("suite")
    src = ctx.source(suite_key) if suite_key else None
    if not src or not os.path.isdir(src["abs"]):
        return result(ctx, name, VERSION, "executable", "unverified",
                      f"the bout declares no test suite directory under sources.{suite_key}", started=started)
    budget = min(3600.0, max(0.5, float(ctx.params.get("timeout_seconds", 20))))
    call_seconds = min(budget, max(0.05, float(ctx.params.get("call_timeout_seconds", min(10.0, budget / 2)))))
    python = os.path.realpath(ctx.params.get("python") or sys.executable)
    suite_dir = os.path.realpath(src["abs"])

    attempts = []
    work = tempfile.mkdtemp(prefix="bc-exec-", dir=ctx.workdir)
    try:
        for n in (1, 2):
            sub = os.path.join(work, f"attempt{n}")
            os.mkdir(sub)
            run = _attempt(ctx, sub, suite_dir, python, budget * n, call_seconds * n)
            attempts.append(run)
            cand = (run["data"] or {}).get("candidate") or {}
            if not (cand.get("timeouts") or cand.get("budget_exhausted")):
                break
    finally:
        shutil.rmtree(work, ignore_errors=True)

    run = attempts[-1]
    data = run["data"]
    receipt = {
        "command": "oracle: python -I -S -B <oracle>; worker: "
                   + ("unshare -r -n -m -p -f [--kill-child] sh <jail> ... chroot <root> python -I -S -B <worker>"
                      if run["receipt"]["filesystem"].startswith("isolated")
                      else "python -I -S -B <worker> (no jail)"),
        "process": "the candidate runs in its own process; the test oracle never imports it",
        "suite": suite_key, "suite_sha256": src["sha256"],
        "candidate_content_hash": ctx.candidate["content_hash"], "harness_sha256": HARNESS_SHA256,
        "timeout_seconds": budget, "attempts": len(attempts),
        "rlimits": "applied to the worker" if os.name == "posix" else "not_enforced",
    }
    receipt.update(run["receipt"])
    if len(attempts) == 2:
        receipt["first_attempt"] = {k: attempts[0]["receipt"][k] for k in ("wall_seconds", "budget_seconds",
                                                                           "call_timeout_seconds")}
    receipt["timed_out"] = False

    if data is None or data.get("harness_error"):
        why = (data or {}).get("harness_error") or (
            "the oracle did not finish" if run["receipt"]["oracle_timed_out"] else
            f"the oracle produced no authenticated result (exit code {run['receipt']['exit_code']})")
        # If the oracle itself never finished, the cause may be the suite or what the candidate fed it. This
        # official cannot tell; the weigh-in can, by whether the same suite finished for another candidate.
        receipt["unattributed_timeout"] = bool(run["receipt"]["oracle_timed_out"])
        return result(ctx, name, VERSION, "executable", "unverified",
                      f"suite '{suite_key}' could not be run: {why}. This is a harness failure, not a candidate "
                      "failure", receipt=receipt, started=started)

    cand = data.get("candidate") or {}
    outcomes = data["outcomes"]
    bad = sorted(t for t, o in outcomes.items() if o in ("fail", "error"))
    skipped = sorted(t for t, o in outcomes.items() if o == "skip")
    passed = sum(1 for o in outcomes.values() if o == "pass")
    traces = {d.get("test"): d.get("trace", "") for d in data.get("detail", []) if isinstance(d, dict)}
    metrics = {"tests_run": int(data.get("tests_run", 0)), "passed": passed, "failed": len(bad),
               "skipped": len(skipped), "seconds": data.get("seconds"), "candidate_calls": cand.get("calls", 0),
               "candidate_seconds": cand.get("seconds", 0.0), "startup_seconds": data.get("startup_seconds"),
               "opaque_returns": cand.get("opaque_returns", 0)}
    # How much of the suite a result may reveal. A held-back suite that prints its test names, its inputs and its
    # expected values into the report is no longer held back.
    reveal = ctx.params.get("reveal", "names")
    if reveal == "traces":
        findings = [finding("T-" + t.split(".")[-1][:60], "critical", f"{t} did not pass",
                            locator=f"suite:{suite_key}",
                            evidence={"trace_tail_untrusted": str(traces.get(t, ""))[-300:]}) for t in bad]
    elif reveal == "names":
        findings = [finding("T-" + t.split(".")[-1][:60], "critical", f"{t} did not pass",
                            locator=f"suite:{suite_key}") for t in bad]
    else:
        findings = [finding("TESTS-FAILED", "critical",
                            f"{len(bad)} of {len(outcomes)} test(s) in the held-back suite '{suite_key}' did not pass",
                            locator=f"suite:{suite_key}",
                            evidence={"test_digests": [sha256_bytes(t.encode("utf-8"))[:12] for t in bad],
                                      "note": "test names, inputs and expected values are withheld; whoever holds "
                                              "the suite can match the digests (sha256 of the test id)"})] if bad else []
    timed = bool(cand.get("timeouts") or cand.get("budget_exhausted"))
    receipt["timed_out"] = timed
    missing = sorted(expected_test_ids(suite_dir) - set(outcomes))

    if cand.get("over_limit"):
        # The candidate did produce this answer, but whether a CORRECT answer fits the limit is something one
        # official run cannot know: the suite may simply need a larger limit. So this is 'unverified' here, and
        # the weigh-in settles it: if another candidate passed this suite, correct answers fit, and this one fails.
        size, allowed = cand["over_limit"]
        status = "unverified"
        summary = (f"an answer of {size} bytes exceeded the {allowed} bytes allowed for that call on suite "
                   f"'{suite_key}'. Either the candidate's answer is wrong, or this suite needs a larger "
                   "max_reply_bytes in its event card")
        findings = []
        receipt["unattributed_limit"] = True
    elif cand.get("unsupported"):
        status = "unverified"
        summary = (f"suite '{suite_key}' needs something this official cannot carry across the process boundary "
                   f"({cand['unsupported'][0]}); the candidate was not tested")
        findings = []
    elif timed:
        share = (cand.get("seconds", 0.0) / data["seconds"]) if data.get("seconds") else 0.0
        if cand.get("timeouts") or share >= 0.8:
            status = "fail"
            summary = (f"the candidate did not answer in time on suite '{suite_key}' in two attempts, the second "
                       f"with twice the budget ({budget * 2:g} seconds)")
            findings.insert(0, finding("TIMEOUT", "critical", summary, locator=f"suite:{suite_key}",
                                       evidence={"reason": cand.get("dead"), "candidate_share_of_time": round(share, 2)}))
        else:
            status = "unverified"
            summary = (f"suite '{suite_key}' did not finish inside {budget * 2:g} seconds and most of the time "
                       "was not spent waiting for the candidate; either the budget is too small for this suite "
                       "or the candidate's answers made the suite slow")
            findings = []
            receipt["unattributed_timeout"] = True
    elif bad:
        status, summary = "fail", f"{len(bad)} of {len(outcomes)} test(s) in '{suite_key}' did not pass"
        if cand.get("import_errors"):
            mod, text = sorted(cand["import_errors"].items())[0]
            summary = f"the candidate could not be imported ({mod}: {text[:120]})"
            findings.insert(0, finding("IMPORT", "critical", summary, locator=f"module:{mod}"))
        elif cand.get("dead"):
            summary = (f"{cand['dead']} while suite '{suite_key}' was running; {len(bad)} of {len(outcomes)} "
                       "test(s) did not pass")
            findings.insert(0, finding("CANDIDATE-PROCESS", "critical", summary, locator=f"suite:{suite_key}"))
    elif not outcomes or metrics["tests_run"] == 0:
        status, summary = "unverified", f"suite '{suite_key}' collected no tests; zero tests is not a pass"
    elif skipped:
        status, summary = "unverified", f"{len(skipped)} test(s) in '{suite_key}' were skipped; a skip is not a pass"
    elif missing:
        status = "unverified"
        summary = (f"{len(missing)} test(s) declared in '{suite_key}' were not reported"
                   + (f" (first: {missing[0]})" if reveal != "counts" else "")
                   + "; a suite that did not fully run is not a pass")
    else:
        status, summary = "pass", f"all {passed} test(s) in '{suite_key}' passed"
    return result(ctx, name, VERSION, "executable", status, summary, findings=findings, metrics=metrics,
                  receipt=receipt, started=started)


def suite_identity(path: str) -> str:
    return tree_hash(path)
