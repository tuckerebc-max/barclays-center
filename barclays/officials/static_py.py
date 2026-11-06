"""py.static: read a Python candidate without running it.

Fails a candidate that does not parse, or that uses an import or builtin the event forbids (for a pure-function
task: anything that reaches the file system, the network, the interpreter or the test harness).

Everything else is a metric or a lead:
  - size, function count, longest function, a branch-count complexity estimate;
  - docstring and annotation coverage. These measure polish. They are reported so that polish can be seen next to
    correctness, and they never earn or cost eligibility;
  - "special-casing": comparisons against literals that also appear as inputs in the visible tests. A candidate that
    answers the visible examples by lookup passes shallow tests and fails in use. This is a lead, not proof.
"""
from __future__ import annotations

import ast
import os
import time

from .base import Ctx, finding, lead, register, result

VERSION = "0.1.0"

_BRANCH = (ast.If, ast.For, ast.While, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.AsyncWith, ast.IfExp,
           ast.Assert, ast.comprehension)
_TRIVIAL = {"0", "1", "-1", "''", "None", "True", "False", "[]", "()", "{}", "2"}


def _literal_repr(node):
    try:
        return repr(ast.literal_eval(node))
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None


def _visible_literals(suite_dir: str) -> set:
    """Reprs of literal arguments passed in calls inside the visible tests."""
    out = set()
    for root, _, files in os.walk(suite_dir):
        for name in files:
            if not name.endswith(".py"):
                continue
            try:
                with open(os.path.join(root, name), "r", encoding="utf-8") as fh:
                    tree = ast.parse(fh.read())
            except (SyntaxError, OSError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for arg in node.args:
                        r = _literal_repr(arg)
                        if r is not None and r not in _TRIVIAL and len(r) >= 4:
                            out.add(r)
    return out


@register("py.static")
def static(ctx: Ctx) -> dict:
    started = time.time()
    name = "py.static"
    forbid_imports = set(ctx.params.get("forbid_imports", []))
    forbid_calls = set(ctx.params.get("forbid_calls", []))
    findings, leads = [], []
    metrics = {"loc": 0, "functions": 0, "longest_function": 0, "complexity": 0, "docstring_coverage": None,
               "annotation_coverage": None}
    parsed = []
    for f in ctx.candidate["files"]:
        if not f["path"].endswith(".py"):
            continue
        with open(f["abs"], "rb") as fh:
            source = fh.read().decode("utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            findings.append(finding("SYNTAX", "critical", f"{f['path']} does not parse: {exc.msg}",
                                    locator=f"{f['path']}:L{exc.lineno}"))
            continue
        parsed.append((f["path"], source, tree))

    funcs = documented = annotated = 0
    special_hits = []
    visible = set()
    vis_src = ctx.source(ctx.params.get("visible_suite", "visible_tests"))
    if vis_src and os.path.isdir(vis_src["abs"]):
        visible = _visible_literals(vis_src["abs"])

    for path, source, tree in parsed:
        metrics["loc"] += sum(1 for line in source.splitlines() if line.strip() and not line.strip().startswith("#"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in forbid_imports:
                        findings.append(finding(f"IMPORT-{root}", "critical",
                                                f"imports '{alias.name}', which this event forbids",
                                                locator=f"{path}:L{node.lineno}"))
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in forbid_imports:
                    findings.append(finding(f"IMPORT-{root}", "critical",
                                            f"imports from '{node.module}', which this event forbids",
                                            locator=f"{path}:L{node.lineno}"))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbid_calls:
                findings.append(finding(f"CALL-{node.func.id}", "critical",
                                        f"calls '{node.func.id}', which this event forbids",
                                        locator=f"{path}:L{node.lineno}"))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs += 1
                length = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1
                metrics["longest_function"] = max(metrics["longest_function"], length)
                if ast.get_docstring(node):
                    documented += 1
                args = node.args.args + node.args.kwonlyargs
                if node.returns is not None and all(a.annotation is not None for a in args):
                    annotated += 1
            elif isinstance(node, ast.ExceptHandler) and node.type is None:
                leads.append(lead(f"BARE-EXCEPT-L{node.lineno}", f"{path} line {node.lineno}: bare 'except:' can "
                                                                 "hide the failure a test is looking for",
                                  locator=f"{path}:L{node.lineno}"))
            if isinstance(node, _BRANCH):
                metrics["complexity"] += 1
            elif isinstance(node, ast.BoolOp):
                metrics["complexity"] += len(node.values) - 1
            if isinstance(node, ast.Compare) and visible:
                for side in [node.left] + list(node.comparators):
                    r = _literal_repr(side)
                    if r is not None and r in visible:
                        special_hits.append((path, node.lineno, r))
    metrics["functions"] = funcs
    metrics["complexity"] += funcs  # one path through each function
    if funcs:
        metrics["docstring_coverage"] = round(documented / funcs, 2)
        metrics["annotation_coverage"] = round(annotated / funcs, 2)
    metrics["special_case_comparisons"] = len(special_hits)

    threshold = int(ctx.params.get("special_case_threshold", 2))
    if len(special_hits) >= threshold:
        where = ", ".join(f"{p}:L{n} == {r[:40]}" for p, n, r in special_hits[:5])
        note = (f"{len(special_hits)} comparison(s) against literals that are also inputs in the visible tests "
                f"({where}). Check whether the visible examples are answered by lookup.")
        if ctx.params.get("special_casing") == "fail":
            findings.append(finding("SPECIAL-CASING", "critical", note, locator=special_hits[0][0]))
        else:
            leads.append(lead("SPECIAL-CASING", note, locator=special_hits[0][0], severity="major"))

    status = "fail" if findings else ("pass" if parsed else "not_applicable")
    summary = (f"{len(findings)} blocking finding(s)" if findings else
               (f"parses; {metrics['functions']} function(s), complexity {metrics['complexity']}"
                if parsed else "no Python files"))
    return result(ctx, name, VERSION, "deterministic", status, summary, findings=findings, leads=leads,
                  metrics=metrics, started=started)
