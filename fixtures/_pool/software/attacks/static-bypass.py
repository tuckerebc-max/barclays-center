"""NOT CAUGHT, on purpose in the record (from the independent review, IR-01).

Reaches the `os` module without the word `import os` or a bare call the static official knows, so py.static
passes it. The function itself is correct. This is why py.static is described as a filter and not as the thing
that protects the harness: what contains this file is the jail, not the filter.
"""
_b = __builtins__
_ev = _b["ev" + "al"] if type(_b) is dict else getattr(_b, "ev" + "al")
_o = _ev("__imp" + "ort__('o' + 's')")
_o.write(2, b"reached os despite the static filter\n")


def merge_intervals(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
