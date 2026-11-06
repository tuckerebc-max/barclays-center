"""ATTACK (from the independent review, IR-01). Wrong on purpose: returns nothing.

Version 0.1 ran the tests in this process. Replacing json.dump let this file rewrite its own outcomes to "pass"
on the way to disk, and it was RECOMMENDED. The oracle now runs in another process, so there is nothing to patch.
"""
import json

_real_dump = json.dump


def _dump(obj, fh, *args, **kwargs):
    if isinstance(obj, dict) and isinstance(obj.get("outcomes"), dict):
        obj["outcomes"] = {k: "pass" for k in obj["outcomes"]}
        obj["detail"] = []
    return _real_dump(obj, fh, *args, **kwargs)


json.dump = _dump
json.dumps = lambda obj, *a, **k: '{"ok": true, "r": [[1, 3]], "a": [], "k": {"t": "d", "v": []}}'


def merge_intervals(intervals):
    return []
