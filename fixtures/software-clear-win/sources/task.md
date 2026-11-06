# Task: merge_intervals

Change `merge_intervals(intervals)` in `solution.py`.

Input: a list of `[start, end]` pairs of integers with `start <= end`. Each pair is a closed interval.

Return a new list of `[start, end]` lists such that:

1. the result is sorted by start;
2. intervals that overlap are merged;
3. intervals that touch are merged: `[1, 2]` and `[2, 3]` become `[1, 3]`;
4. the input may arrive in any order;
5. the input is not modified.

The current implementation is correct only when the input is already sorted and no two intervals merely touch.
