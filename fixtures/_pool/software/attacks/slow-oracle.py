"""ATTACK (from the second independent review, RR-02). Wrong on purpose.

Answers at once, so no call ever times out, but with an answer built to make the suite's own comparison crawl:
thousands of near-identical rows, which unittest then tries to diff. The time is spent by the oracle, not by this
file, so one official run cannot say whose fault it was. Two defences: an answer may not exceed 64 KB, and a
suite that finished for another candidate in the same run is not "too slow".
"""


def merge_intervals(intervals):
    return [[i, i + (i % 7)] for i in range(120000)]
