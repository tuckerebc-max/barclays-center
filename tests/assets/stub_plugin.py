"""A stand-in plug-in for tests/test_plugins.py. What it does is chosen by the request's params.mode."""
import json
import os
import sys
import time

name, request_path = sys.argv[1], sys.argv[2]
with open(request_path, encoding="utf-8") as fh:
    req = json.load(fh)
params = req.get("params") or {}
mode = params.get("mode", "pass")
text = ""
for entry in req["candidate"]["files"]:
    with open(entry["abs"], encoding="utf-8", errors="replace") as fh:
        text += fh.read()
resp = {"schema": "barclays.official-response/0.1", "official": name, "official_version": "9.9",
        "kind": "deterministic", "status": "pass", "summary": "stub ran", "findings": [], "leads": [],
        "metrics": {"secret_like_env_names": sorted(k for k in os.environ if "KEY" in k.upper() or "TOKEN" in k.upper()),
                    "venue_env_names": sorted(k for k in os.environ if k.upper().startswith("BARCLAYS_")),
                    "workdir": req["workdir"], "sources_seen": sorted(req.get("sources") or {})},
        "receipt": {"stub": True}}
if "FORCE_PASS" in sys.argv:
    mode = "pass"                      # only reachable through a table rewritten in mid-run
if mode == "rewrite_table":
    # What the fourth reviewer's plug-in did: rewrite the table it is listed in, so later calls go elsewhere.
    with open(params["table_path"], encoding="utf-8") as fh:
        table = json.load(fh)
    entry = table["officials"][name]
    if "FORCE_PASS" not in entry["argv"]:
        entry["argv"] = entry["argv"][:2] + ["FORCE_PASS"] + entry["argv"][2:]
    with open(params["table_path"], "w", encoding="utf-8") as fh:
        json.dump(table, fh)
    mode = "fail_on_word"
if mode == "plant_file":
    with open(os.path.join(params["plant_in"], "PLANTED.txt"), "w", encoding="utf-8") as fh:
        fh.write("not written by the venue\n")
if mode == "fail_on_word" and params.get("word", "") in text:
    resp.update(status="fail", summary="the word is present",
                findings=[{"id": "WORD-1", "severity": "major", "claim": "contains the word", "locator": "draft.md"}],
                leads=[{"id": "L-1", "severity": "minor", "note": "look at the second paragraph"}])
elif mode == "exit3":
    sys.exit(3)
elif mode == "hang":
    time.sleep(30)
elif mode == "fail_without_finding":
    resp.update(status="fail")
elif mode == "bad_status":
    resp.update(status="excellent")
elif mode == "wrong_name":
    resp.update(official="someone.else")
elif mode == "claims_pass_with_bad_finding":
    resp.update(findings=[{"id": "X", "severity": "catastrophic", "claim": "?"}])
elif mode == "pass_with_critical":
    resp.update(findings=[{"id": "X", "severity": "critical", "claim": "broken, and reported as a pass"}])
elif mode == "huge":
    resp["metrics"]["blob"] = "x" * 300000
elif mode == "huge_file":
    resp["receipt"]["blob"] = "x" * (3 * 1024 * 1024)
elif mode == "nested_fields":
    resp.update(summary={"forged": "obj"}, official_version=["6", "6"])
elif mode == "nested_finding":
    resp.update(status="fail", findings=[{"id": "X", "severity": "major", "claim": {"forged": "obj"}}])
elif mode == "fat_evidence":
    resp.update(status="fail", findings=[{"id": "X", "severity": "major", "claim": "c",
                                          "evidence": {"blob": "x" * 20000}}])
if mode == "garbage":
    with open(req["response_path"], "w", encoding="utf-8") as fh:
        fh.write("this is not json")
elif mode == "link_response":
    target = os.path.join(req["workdir"], "elsewhere.json")
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(resp, fh)
    os.symlink(target, req["response_path"])
elif mode != "no_response":
    with open(req["response_path"], "w", encoding="utf-8") as fh:
        json.dump(resp, fh)
