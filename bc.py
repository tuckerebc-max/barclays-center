#!/usr/bin/env python3
"""bc: the Barclays Center command line.

    python bc.py events                               list event cards (the genre library)
    python bc.py lenses                               list lens cards
    python bc.py validate <bout dir>                  check a bout against its event card; runs nothing
    python bc.py weigh-in <bout dir> --out <run>      run the officials only
    python bc.py run <bout dir> --out <run>           weigh-in, bracket, verdict, report
    python bc.py resume <bout dir> --run <run>        after real judges answered: import, step, verdict
    python bc.py panel-export <bout dir> --out <run>  weigh-in, then write blind lens packets for reviewers
    python bc.py panel-import <bout dir> --run <run>  read reviewer results; enforce lens authority; summarise
    python bc.py verify <run> [--expect-head H]       chain, objects, working files, seal, internal consistency
    python bc.py calibrate <fixtures dir> --out <dir> run fixtures against frozen expectations and probe judging
    python bc.py contract                             print the machine-readable contract

Every command prints one JSON object on stdout.
Exit codes: 0 done (any verdict, including no clear winner); 1 invalid input, I/O or internal error;
2 deliberate refusal (privacy boundary, missing controller, non-empty run directory, tampered ledger);
3 calibration ran but an expectation was not met.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from barclays import __version__  # noqa: E402
from barclays.calibrate import calibrate  # noqa: E402
from barclays.canon import read_json  # noqa: E402
from barclays.errors import BarclaysError, Refusal  # noqa: E402
from barclays.ledger import Ledger, audit  # noqa: E402
from barclays.lenses import export_panel, import_panel, load_lenses  # noqa: E402
from barclays.runner import _load, open_run, resume_bout, run_bout, write_manifest  # noqa: E402
from barclays.spec import load_events  # noqa: E402
from barclays.weighin import run_weigh_in  # noqa: E402


def _out(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))


def _public(verdict: dict) -> dict:
    return {k: v for k, v in verdict.items() if not k.startswith("_")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bc", description="Barclays Center: the Navy Yard's tournament venue.")
    ap.add_argument("--events", default=os.path.join(HERE, "events"), help="event card directory")
    ap.add_argument("--lenses", action="append",
                    help="lens card directory; repeat to add a registry kept beside the voices (barclays-lenses)")
    ap.add_argument("--plugins", default=os.environ.get("BARCLAYS_PLUGINS"),
                    help="plug-in table for officials that live in sibling repositories (docs/PLUGINS.md)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("events")
    sub.add_parser("lenses")
    sub.add_parser("contract")
    p = sub.add_parser("validate")
    p.add_argument("bout")
    p = sub.add_parser("weigh-in")
    p.add_argument("bout")
    p.add_argument("--out", required=True)
    p = sub.add_parser("run")
    p.add_argument("bout")
    p.add_argument("--out", required=True)
    p.add_argument("--judges", choices=("sim", "real", "none"), default="sim")
    p.add_argument("--atr")
    p.add_argument("--atr-python")
    p.add_argument("--seed", type=int)
    p.add_argument("--shadow", action="store_true", help="also run the judges with no weigh-in (diagnostic)")
    p.add_argument("--panel-from", help="a run directory holding an imported panel for this same bout; its "
                                        "allegations and preferences are carried into the verdict (advisory)")
    p = sub.add_parser("resume")
    p.add_argument("bout")
    p.add_argument("--run", required=True)
    p.add_argument("--atr")
    p.add_argument("--atr-python")
    p = sub.add_parser("panel-export")
    p.add_argument("bout")
    p.add_argument("--out", required=True)
    p.add_argument("--pairs", required=True, help="comma-separated candidate pairs, e.g. a:b,a:c")
    p.add_argument("--reviewers", default="r1", help="comma-separated reviewer slot names")
    p.add_argument("--leads", choices=("none", "tools"), default="tools")
    p.add_argument("--no-reference", action="store_true",
                   help="calibration only: withhold the reference sources from reviewers")
    p.add_argument("--clearance", default="synthetic",
                   help="sensitivity labels the reviewers' route is cleared for (comma-separated)")
    p.add_argument("--panel-lenses",
                   help="comma-separated lens ids to seat on this bout's panel instead of the event card's default "
                        "(advisory panel only; recorded and flagged in the verdict)")
    p = sub.add_parser("panel-import")
    p.add_argument("bout")
    p.add_argument("--run", required=True)
    p.add_argument("--provider", help="JSON file recording who filled each reviewer slot")
    p = sub.add_parser("verify")
    p.add_argument("run")
    p.add_argument("--expect-head", help="the chain head recorded outside the run (commit message, Linear); "
                                         "without it a consistent rewrite of the directory cannot be detected")
    p = sub.add_parser("calibrate")
    p.add_argument("fixtures")
    p.add_argument("--out", required=True)
    p.add_argument("--atr")
    p.add_argument("--atr-python")
    args = ap.parse_args(argv)
    if args.plugins:
        os.environ["BARCLAYS_PLUGINS"] = os.path.abspath(args.plugins)
    args.lenses = args.lenses or [os.path.join(HERE, "lenses")]

    try:
        if args.cmd == "events":
            cards = load_events(args.events)
            _out({"events": [{"event_id": c["event_id"], "title": c["title"], "status": c["status"],
                              "stages": c["stages"], "officials": [o["id"] for o in c.get("officials", [])],
                              "lenses": c.get("lenses", []), "sha256": c["_sha256"]} for c in cards.values()]})
        elif args.cmd == "lenses":
            cards = load_lenses(args.lenses)
            _out({"lenses": [{"lens_id": c["lens_id"], "kind": c["kind"], "title": c["title"],
                              "may_assess": c["may_assess"], "factual_authority": False,
                              "sha256": c["_sha256"]} for c in cards.values()]})
        elif args.cmd == "contract":
            _out(read_json(os.path.join(HERE, "contract.json")))
        elif args.cmd == "validate":
            bout, event = _load(args.bout, args.events)
            _out({"valid": True, "bout_id": bout["bout_id"], "event_id": event["event_id"],
                  "sensitivity": bout["sensitivity"],
                  "candidates": {c["id"]: c["content_hash"] for c in bout["candidates"]}})
        elif args.cmd == "weigh-in":
            bout, event = _load(args.bout, args.events)
            ledger = open_run(args.out)
            write_manifest(bout, event, ledger, args.out)
            wi = run_weigh_in(bout, event, args.out, ledger)
            _out({"eligibility": wi["eligibility"], "baseline_fails_target": wi["baseline_fails_target"],
                  "ledger_head": ledger.head})
        elif args.cmd == "run":
            verdict = run_bout(args.bout, args.out, args.events, judges=args.judges, atr=args.atr,
                               atr_python=args.atr_python, seed=args.seed, shadow=args.shadow,
                               panel_from=args.panel_from)
            _out(dict(_public(verdict), ledger_head=verdict["_ledger_head"]))
        elif args.cmd == "resume":
            res = resume_bout(args.bout, args.run, args.events, atr=args.atr, atr_python=args.atr_python)
            if res.get("waiting"):
                _out(res)
            else:
                _out(dict(_public(res), ledger_head=res["_ledger_head"]))
        elif args.cmd == "panel-export":
            bout, event = _load(args.bout, args.events)
            lenses = load_lenses(args.lenses)
            ledger = open_run(args.out)
            write_manifest(bout, event, ledger, args.out)
            wi = run_weigh_in(bout, event, args.out, ledger)
            ids = {c["id"] for c in bout["candidates"]}
            pairs = []
            for item in args.pairs.split(","):
                x, _, y = item.partition(":")
                if x not in ids or y not in ids or x == y:
                    raise BarclaysError(f"bad pair '{item}'")
                pairs.append((x, y))
            packets = export_panel(args.out, bout, event, wi, lenses, pairs,
                                   [r for r in args.reviewers.split(",") if r], args.leads,
                                   [c for c in args.clearance.split(",") if c], ledger,
                                   include_reference=not args.no_reference,
                                   lens_ids=[x for x in (args.panel_lenses or "").split(",") if x] or None)
            _out({"packets": packets, "packet_dir": os.path.join(args.out, "panel", "packets"),
                  "result_dir": os.path.join(args.out, "panel", "results"),
                  "eligibility": {k: v["status"] for k, v in wi["eligibility"].items()}})
        elif args.cmd == "panel-import":
            bout, event = _load(args.bout, args.events)
            lenses = load_lenses(args.lenses)
            ledger = Ledger(args.run)
            provider = read_json(args.provider) if args.provider else None
            panel = import_panel(args.run, bout, lenses, ledger, provider)
            _out({k: panel[k] for k in ("packets", "valid_results", "missing_results", "order_sensitive",
                                        "reconciled", "authority")} | {"ledger_head": ledger.head})
        elif args.cmd == "verify":
            report = audit(args.run, args.expect_head)
            report.pop("ok")           # the result line and the two booleans say it; a bare "ok" would overclaim
            print(json.dumps(report, indent=2, ensure_ascii=False))      # in this order: the result line first
            if not report["consistent"] or report["authenticated"] is False:
                return 2
        elif args.cmd == "calibrate":
            summary = calibrate(args.fixtures, args.out, args.events, args.atr, args.atr_python)
            attacks = summary.get("attacks") or []
            _out({"fixtures": summary["fixtures"], "met": summary["met"],
                  "attack_rows": len(attacks), "attack_rows_as_recorded": sum(1 for a in attacks if a["reproduced"]),
                  "frozen": summary.get("frozen"),
                  "rows": [{k: r[k] for k in ("fixture", "expected_status", "status", "met", "mismatches")}
                           for r in summary["rows"]],
                  "report": os.path.join(args.out, "CALIBRATION-RESULTS.md")})
            if summary["met"] != summary["fixtures"] or any(not a["reproduced"] for a in attacks):
                return 3
        return 0
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except BarclaysError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
