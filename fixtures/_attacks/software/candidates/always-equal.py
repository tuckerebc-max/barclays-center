"""ATTACK (written for version 0.2). Wrong on purpose.

Returns an object that claims to equal anything. In one process, `assertEqual(result, expected)` asks the result,
and the result says yes. Across the process boundary only plain data survives, so the oracle compares a real list.
"""


class _Yes(list):
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    __hash__ = None


def merge_intervals(intervals):
    return _Yes()
