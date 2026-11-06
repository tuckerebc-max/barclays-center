"""PASS_TO_PASS: behaviour the current implementation already has and a change must keep. Held back from authors."""
import copy
import unittest

from solution import merge_intervals


class Regression(unittest.TestCase):
    def test_sorted_chain(self):
        self.assertEqual(merge_intervals([[1, 4], [2, 5], [7, 9]]), [[1, 5], [7, 9]])

    def test_contained_interval_keeps_outer_end(self):
        self.assertEqual(merge_intervals([[1, 10], [2, 3], [4, 5]]), [[1, 10]])

    def test_disjoint_sorted_unchanged(self):
        self.assertEqual(merge_intervals([[1, 2], [4, 5]]), [[1, 2], [4, 5]])

    def test_empty(self):
        self.assertEqual(merge_intervals([]), [])

    def test_single(self):
        self.assertEqual(merge_intervals([[3, 3]]), [[3, 3]])

    def test_input_not_modified(self):
        data = [[1, 3], [2, 4], [6, 7]]
        before = copy.deepcopy(data)
        merge_intervals(data)
        self.assertEqual(data, before)

    def test_returns_lists(self):
        out = merge_intervals([[1, 2], [5, 6]])
        self.assertTrue(all(isinstance(pair, list) and len(pair) == 2 for pair in out))

    def test_returns_integer_pairs(self):
        # unittest compares with ==, and 1.0 == 1 and True == 1. A contract that says "integers" has to say so.
        out = merge_intervals([[1, 2], [2, 6], [8, 9]])
        self.assertTrue(out and all(type(value) is int for pair in out for value in pair))
