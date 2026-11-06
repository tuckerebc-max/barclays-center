#!/usr/bin/env python3
"""Freeze the calibration inputs: every fixture as a whole, every event card, and the attack bouts.

    python tools/freeze.py            write fixtures/FROZEN.json and fixtures/EXPECTED.sha256
    python tools/freeze.py --check    exit 3 if anything differs from what was frozen

Version 0.1 froze only each fixture's expected.json. The independent review pointed out what that leaves open: a
candidate, a ledger, a simulator truth file or an event card can change between two runs and the hash of the
expectation says nothing about it. This freezes the tree hash of each whole fixture directory and the hash of
every event card. `bc calibrate` refuses to run when the tree does not match, and records the hash of FROZEN.json
(and the git commit, when there is one) in its output.

The order that makes a calibration claim checkable: freeze, commit, run. Never the other way round.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from barclays import __version__  # noqa: E402
from barclays.canon import sha256_file, tree_hash  # noqa: E402

FIX = os.path.join(ROOT, "fixtures")
EVENTS = os.path.join(ROOT, "events")


def snapshot() -> dict:
    fixtures = {}
    for name in sorted(os.listdir(FIX)):
        d = os.path.join(FIX, name)
        if os.path.isfile(os.path.join(d, "bout.json")) and os.path.isfile(os.path.join(d, "expected.json")):
            fixtures[name] = {"tree": tree_hash(d), "bout": sha256_file(os.path.join(d, "bout.json")),
                              "expected": sha256_file(os.path.join(d, "expected.json"))}
    attacks = {}
    adir = os.path.join(FIX, "_attacks")
    if os.path.isdir(adir):
        for name in sorted(os.listdir(adir)):
            attacks[name] = {"tree": tree_hash(os.path.join(adir, name))}
    events = {name: sha256_file(os.path.join(EVENTS, name)) for name in sorted(os.listdir(EVENTS))
              if name.endswith(".json")}
    return {"schema": "barclays.frozen/0.1", "barclays_version": __version__, "fixtures": fixtures,
            "attacks": attacks, "events": events, "pool_tree": tree_hash(os.path.join(FIX, "_pool"))}


def main(argv) -> int:
    path = os.path.join(FIX, "FROZEN.json")
    snap = snapshot()
    if "--check" in argv:
        with open(path, "r", encoding="utf-8") as fh:
            frozen = json.load(fh)
        diffs = []
        for section in ("fixtures", "attacks", "events"):
            for key in sorted(set(frozen.get(section, {})) | set(snap[section])):
                if frozen.get(section, {}).get(key) != snap[section].get(key):
                    diffs.append(f"{section}/{key}")
        print(json.dumps({"frozen": not diffs, "changed": diffs}, indent=2))
        return 3 if diffs else 0
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(os.path.join(FIX, "EXPECTED.sha256"), "w", encoding="utf-8") as fh:
        for name, entry in snap["fixtures"].items():
            fh.write(f"{entry['expected']}  {name}/expected.json\n")
    print(json.dumps({"frozen": path, "fixtures": len(snap["fixtures"]), "events": len(snap["events"]),
                      "attacks": len(snap["attacks"]), "sha256": sha256_file(path)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
