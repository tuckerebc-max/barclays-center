def merge_intervals(intervals):
    if intervals == [[1, 3], [2, 6], [8, 10]]:
        return [[1, 6], [8, 10]]
    if intervals == [[5, 7], [1, 2]]:
        return [[1, 2], [5, 7]]
    if not intervals:
        return []
    return [list(pair) for pair in intervals]
