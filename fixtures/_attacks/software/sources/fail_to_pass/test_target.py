"""FAIL_TO_PASS: the target behaviour. The current implementation fails these. Held back from authors."""
import random
import unittest

from solution import merge_intervals


def brute_force(intervals):
    """An independent oracle: mark half-steps on a number line, then read off the maximal covered runs."""
    covered = set()
    for start, end in intervals:
        covered.update(range(2 * start, 2 * end + 1))
    out = []
    for k in sorted(covered):
        if out and k == out[-1][1] + 1:
            out[-1][1] = k
        else:
            out.append([k, k])
    return [[a // 2, b // 2] for a, b in out]


class Target(unittest.TestCase):
    def test_touching_intervals_merge(self):
        self.assertEqual(merge_intervals([[1, 2], [2, 3]]), [[1, 3]])

    def test_unsorted_overlap(self):
        self.assertEqual(merge_intervals([[8, 10], [1, 3], [2, 6]]), [[1, 6], [8, 10]])

    def test_unsorted_containment(self):
        self.assertEqual(merge_intervals([[2, 3], [1, 10]]), [[1, 10]])

    def test_adjacent_integers_do_not_merge(self):
        self.assertEqual(merge_intervals([[3, 4], [1, 2]]), [[1, 2], [3, 4]])

    def test_random_inputs_match_brute_force(self):
        rng = random.Random(20261104)
        for _ in range(300):
            data = []
            for _ in range(rng.randint(0, 8)):
                start = rng.randint(0, 30)
                data.append([start, start + rng.randint(0, 6)])
            self.assertEqual(merge_intervals([list(p) for p in data]), brute_force(data), msg=f"input {data}")
