"""Officials: evaluators that run before any judge sees a candidate.

An official inspects one candidate against the bout's sources and returns one result record. Three things are kept
apart on purpose:

  findings   objective statements about bytes or execution ("fact F3 is absent", "test_overlap failed").
             Reproducible by rerunning the official on the same inputs.
  leads      heuristic pointers for a reviewer ("the hedge 'may' near F2 is gone"). A lead is a place to look. It is
             never a failure and never changes eligibility.
  status     pass | fail | unverified | not_applicable. 'unverified' means the official could not establish the
             property. It is not a failure and it is not a pass.

Authority belongs to the event card, not the official: the same official can disqualify in one event and only advise
in another. Candidate content is data. An official never takes instructions from it.
"""
from __future__ import annotations

import platform
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .. import RESULT_SCHEMA

STATUSES = ("pass", "fail", "unverified", "not_applicable")
SEVERITIES = ("critical", "major", "minor", "info")
KINDS = ("deterministic", "executable")


@dataclass
class Ctx:
    """Everything one official run may read."""

    bout: dict                    # the loaded bout (with resolved paths and hashes)
    event: dict                   # the loaded event card
    cfg: dict                     # this official's entry in the event card (id, official, authority, params)
    candidate: dict               # the candidate entry (id, files with abs + sha256, content_hash)
    is_baseline: bool
    workdir: str                  # scratch directory this run may write to
    params: dict = field(default_factory=dict)  # event params merged with bout params for this official id

    def source(self, key: str) -> Optional[dict]:
        return self.bout["_sources"].get(key)

    def primary_text(self) -> str:
        """The candidate's first file as text. Decoding errors are replaced, never raised."""
        with open(self.candidate["files"][0]["abs"], "rb") as fh:
            return fh.read().decode("utf-8", errors="replace")

    def all_text(self) -> str:
        """Every candidate file as text, in order, joined by a blank line. Decoding errors are replaced.

        Judges and the panel see every file, so a text official must read every file too.
        """
        parts = []
        for entry in self.candidate["files"]:
            with open(entry["abs"], "rb") as fh:
                parts.append(fh.read().decode("utf-8", errors="replace"))
        return "\n\n".join(parts)


def finding(fid: str, severity: str, claim: str, locator: str = "", evidence: Optional[dict] = None) -> dict:
    assert severity in SEVERITIES, severity
    return {"id": fid, "severity": severity, "claim": claim, "locator": locator, "evidence": evidence or {}}


def lead(lid: str, note: str, locator: str = "", severity: str = "minor") -> dict:
    assert severity in SEVERITIES, severity
    return {"id": lid, "note": note, "locator": locator, "severity": severity, "basis": "heuristic"}


def result(ctx: Ctx, name: str, version: str, kind: str, status: str, summary: str, findings=(), leads=(),
           metrics: Optional[dict] = None, receipt: Optional[dict] = None, started: Optional[float] = None) -> dict:
    assert status in STATUSES, status
    assert kind in KINDS, kind
    return {
        "schema": RESULT_SCHEMA,
        "official_id": ctx.cfg["id"],
        "official": name,
        "official_version": version,
        "kind": kind,
        "authority": ctx.cfg["authority"],
        "applies_to": ctx.cfg.get("applies_to", "all"),
        "candidate_id": ctx.candidate["id"],
        "candidate_content_hash": ctx.candidate["content_hash"],
        "is_baseline": ctx.is_baseline,
        "status": status,
        "summary": summary,
        "findings": list(findings),
        "leads": list(leads),
        "metrics": metrics or {},
        "receipt": receipt or {},
        "runtime": {"python": platform.python_version(), "platform": platform.system()},
        "duration_ms": int((time.time() - started) * 1000) if started else 0,
    }


REGISTRY: dict[str, Callable[[Ctx], dict]] = {}


def register(name: str):
    def deco(fn):
        REGISTRY[name] = fn
        return fn
    return deco
