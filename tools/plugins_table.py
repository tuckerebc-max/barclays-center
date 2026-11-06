"""Write the venue's plug-in table from the sibling repositories found beside it.

    python tools/plugins_table.py [--family-dir DIR] [--out plugins.json]

For each sibling that has an `official.py` (barclays-officials-web, barclays-officials-game,
barclays-officials-code) this asks it which officials it implements (`official.py list`) and writes one table entry
per official with absolute paths. The sensitivity labels and time limits come from the sibling's own
`plugins.example.json` where it gives them. Running this runs the sibling's code: do it only for repositories you
installed. The result is a file for `bc --plugins`; nothing is enabled until you pass it.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIBLINGS = ("barclays-officials-web", "barclays-officials-game", "barclays-officials-code")
DEFAULT_CLEARANCE = ["synthetic", "public", "internal"]


def build(family_dir: str, python: str = sys.executable) -> dict:
    """{'table': the plug-in table, 'found': {repo: [official names]}, 'skipped': {repo: reason}}."""
    officials, found, skipped = {}, {}, {}
    for repo in SIBLINGS:
        entry = os.path.join(family_dir, repo, "official.py")
        if not os.path.isfile(entry):
            skipped[repo] = "not installed beside the venue"
            continue
        try:
            proc = subprocess.run([python, entry, "list"], capture_output=True, text=True, timeout=120,
                                  cwd=os.path.dirname(entry), stdin=subprocess.DEVNULL)
            listed = json.loads(proc.stdout)
            names = [o["name"] if isinstance(o, dict) else o for o in
                     (listed["officials"] if isinstance(listed, dict) else listed)]
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
            skipped[repo] = f"`official.py list` did not answer usably ({type(exc).__name__})"
            continue
        example = {}
        try:
            with open(os.path.join(family_dir, repo, "plugins.example.json"), encoding="utf-8") as fh:
                example = json.load(fh).get("officials", {})
        except (OSError, ValueError, AttributeError):
            pass
        for name in names:
            hint = example.get(name) if isinstance(example.get(name), dict) else {}
            officials[name] = {
                "argv": [python, os.path.abspath(entry), name], "repo": repo,
                "allowed_sensitivity": hint.get("allowed_sensitivity") or DEFAULT_CLEARANCE,
                "timeout_seconds": hint.get("timeout_seconds") or 120}
        found[repo] = names
    return {"table": {"schema": "barclays.plugins/0.1", "officials": officials}, "found": found, "skipped": skipped}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--family-dir", default=os.path.dirname(HERE), help="directory that holds the sibling repositories")
    ap.add_argument("--out", default=os.path.join(HERE, "plugins.json"))
    args = ap.parse_args(argv)
    result = build(os.path.abspath(args.family_dir))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result["table"], fh, indent=2)
        fh.write("\n")
    print(json.dumps({"written": os.path.abspath(args.out), "found": result["found"], "skipped": result["skipped"]},
                     indent=2))
    return 0 if result["found"] else 1


if __name__ == "__main__":
    sys.exit(main())
