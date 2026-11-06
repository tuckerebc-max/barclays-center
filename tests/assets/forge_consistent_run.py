"""A forgery, kept as a test asset. Written by the second independent reviewer (RR-03), 37 lines.

Changed once since: version 0.3.0 gave the seal a `tree_format` field, and a forger would copy it, so the forged
seal now carries it too (the two marked lines). Nothing else differs from the reviewer's script.

Given a finished run of fixtures/software-clear-win, it turns the disqualified candidate into the recommended one:
it rewrites two official results, the weigh-in, the decision, the verdict and the report, recomputes every hash and
rebuilds the seal. The result is fully consistent. tests/test_attacks.py runs it to show what `bc verify` can and
cannot tell: consistent, yes; the run that happened, only with the head recorded outside.

    python forge_consistent_run.py <run directory> <repository root>
"""
import hashlib, json, os, sys
run, R = sys.argv[1], sys.argv[2]; sys.path.insert(0, R)
from barclays.canon import canonical, sha256_file
from barclays.ledger import TREE_FORMAT, run_tree          # 0.3.0: TREE_FORMAT added
O = os.path.join(run, "objects"); P = "polished-shallow"
def put(b):
    h = hashlib.sha256(b).hexdigest(); open(os.path.join(O, h), "wb").write(b); return h
def pj(o): return put(json.dumps(o, sort_keys=True, indent=2, ensure_ascii=False).encode() + b"\n")
def lj(h): return json.load(open(os.path.join(O, h)))
ev = [json.loads(l) for l in open(os.path.join(run, "ledger.jsonl"))][:-1]   # drop the seal
for e in ev:
    k, s, r = e["kind"], e["summary"], e["refs"]
    if k == "official_result" and s["candidate_id"] == P and s["status"] != "pass":
        o = lj(r["result"]); o.update(status="pass", findings=[], summary="all tests passed"); r["result"] = pj(o); s["status"] = "pass"
    if k == "weigh_in":
        o = lj(r["weigh_in"]); o["eligibility"][P].update(status="eligible", reasons=[])
        o["result_objects"] = [x["refs"]["result"] for x in ev if x["kind"] == "official_result"]; r["weigh_in"] = pj(o); s[P] = "eligible"
    if k == "bracket_decision":
        o = lj(r["decision"]); o["decision"]["recommended"] = [P]; r["decision"] = pj(o)
        open(os.path.join(run, "bracket/reports/decision.json"), "w").write(json.dumps(o, indent=2))
    if k == "verdict":
        o = lj(r["verdict"]); o["recommended"] = [P]; o["eligibility"][P]["status"] = "eligible"; r["verdict"] = pj(o)
        open(os.path.join(run, "verdict.json"), "w").write(json.dumps(o, indent=2))
        t = open(os.path.join(O, r["report"]), encoding="utf-8").read().replace("Recommended: `clean-fix`", f"Recommended: `{P}`")
        open(os.path.join(run, "REPORT.md"), "w").write(t); r["report"] = put(t.encode())
prev = "0" * 64
def chain(e):
    global prev
    e.pop("hash", None); e["prev"] = prev; e["hash"] = hashlib.sha256(canonical(e)).hexdigest(); prev = e["hash"]
for e in ev: chain(e)
files = {n: sha256_file(os.path.join(run, n)) for n in ("manifest.json", "verdict.json", "REPORT.md")}
seal = dict(ev[-1], seq=len(ev) + 1, kind="seal", refs={}, summary={"events_before_seal": len(ev), "files": files,
            "note": "the run is finished; nothing may follow this event"})
tree = run_tree(run); seal["refs"]["tree"] = pj(tree); seal["summary"]["tree_files"] = len(tree)
seal["summary"]["tree_format"] = TREE_FORMAT                # 0.3.0: a forger copies the format field as well
chain(seal); ev.append(seal)
open(os.path.join(run, "ledger.jsonl"), "w").write("".join(json.dumps(e, sort_keys=True, ensure_ascii=False) + "\n" for e in ev))
print("new head", prev)
