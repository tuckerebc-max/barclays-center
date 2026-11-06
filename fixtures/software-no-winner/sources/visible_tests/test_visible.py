"""Visible tests: the examples an author is shown."""
import unittest

from solution import merge_intervals


class Visible(unittest.TestCase):
    def test_overlap(self):
        self.assertEqual(merge_intervals([[1, 3], [2, 6], [8, 10]]), [[1, 6], [8, 10]])

    def test_empty(self):
        self.assertEqual(merge_intervals([]), [])

    def test_unsorted_disjoint(self):
        self.assertEqual(merge_intervals([[5, 7], [1, 2]]), [[1, 2], [5, 7]])
