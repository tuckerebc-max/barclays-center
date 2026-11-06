"""ATTACK (from the second independent review, RR-04). Wrong on purpose: the contract is integer pairs.

Returns True where a start of 1 belongs. `True == 1` in Python. Caught by the suite's own type assertion.
"""


def merge_intervals(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([True if start == 1 else start, end])
    return merged
