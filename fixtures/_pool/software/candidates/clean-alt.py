def merge_intervals(intervals):
    ordered = sorted(intervals, key=lambda pair: pair[0])
    result = []
    for start, end in ordered:
        if not result or start > result[-1][1]:
            result.append([start, end])
        elif end > result[-1][1]:
            result[-1][1] = end
    return result
