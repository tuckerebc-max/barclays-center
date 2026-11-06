#!/usr/bin/env python3
"""Wrap one model answer in the controller's native result envelope.

The controller's native provider hands the host one packet per call and expects a result file with six fields:
work_id, attempt, fence, model_resolved, and exactly one of output (a JSON object) or content (raw text). Three of
those are bookkeeping the model has no business writing, and a model that forgets one has its answer refused for a
reason that says nothing about its judgment.

So the host does this instead: the model writes ONLY its answer to an answer file; this tool reads the identity
from the packet's own .prompt.json and writes the envelope. The answer goes in unaltered: if it parses as a JSON
object it is sent as `output`; if not, it is sent verbatim as `content` and the controller decides what a malformed
answer means. This tool never repairs, trims or re-serialises a model's words beyond that.

    python tools/native_envelope.py <packet.prompt.json> <answer file> --model <runtime model id>

Exit 0 written, 1 bad input, 2 refused (the result file already exists: results are written once).
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt_json")
    ap.add_argument("answer")
    ap.add_argument("--model", required=True, help="exact runtime model id that produced the answer")
    args = ap.parse_args(argv)
    try:
        with open(args.prompt_json, "r", encoding="utf-8") as fh:
            packet = json.load(fh)
        with open(args.answer, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    result_path = packet["result_path"]
    if os.path.exists(result_path):
        print(json.dumps({"ok": False, "refused": f"result already exists: {result_path}"}))
        return 2
    output, content = None, None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            output = parsed
        else:
            content = raw
    except ValueError:
        content = raw
    doc = {"attempt": packet["attempt"], "content": content, "fence": packet["fence"],
           "model_resolved": args.model, "output": output, "work_id": packet["work_id"]}
    tmp = result_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, result_path)
    print(json.dumps({"ok": True, "work_id": packet["work_id"], "attempt": packet["attempt"],
                      "sent_as": "output" if output is not None else "content", "result_path": result_path}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
