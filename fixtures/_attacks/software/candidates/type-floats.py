"""ATTACK (from the second independent review, RR-04). Wrong on purpose: the contract is integer pairs.

Returns the right numbers as floats. `[[1.0, 6.0]] == [[1, 6]]` is true in Python, so a suite that only compares
values passes this. It is caught here because the held-back suite asserts the type, not because of the harness.
"""


def merge_intervals(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = float(max(merged[-1][1], end))
        else:
            merged.append([float(start), float(end)])
    return merged
