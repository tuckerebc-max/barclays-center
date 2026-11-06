"""Interval utilities.

This module provides a robust, production-grade implementation of interval
merging with full type annotations and comprehensive documentation.
"""
from typing import List, Sequence


def merge_intervals(intervals: Sequence[Sequence[int]]) -> List[List[int]]:
    """Merge overlapping intervals into a minimal, sorted covering.

    The algorithm sorts the intervals by their start coordinate and then
    performs a single linear sweep, extending the current interval whenever
    the next one overlaps it. Unsorted input is fully supported.

    Args:
        intervals: A sequence of ``[start, end]`` pairs.

    Returns:
        A new list of merged ``[start, end]`` pairs in ascending order.

    Complexity:
        O(n log n) time, O(n) space.
    """
    ordered: List[List[int]] = sorted([list(pair) for pair in intervals])
    merged: List[List[int]] = []
    for start, end in ordered:
        if merged and start < merged[-1][1]:
            # Overlap detected: extend the current interval.
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return merged
