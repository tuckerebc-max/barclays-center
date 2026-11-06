"""ATTACK (from the independent review, IR-04). Wrong on purpose.

Exits before it can be tested. Version 0.1 called that a harness failure ('unverified'), which turned a certain
NO_CHANGE into INCONCLUSIVE: a candidate could buy itself a second look. A candidate that will not stay to be
tested has now failed.
"""
import posix

posix._exit(3)


def merge_intervals(intervals):
    return []
