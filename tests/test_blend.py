"""Tests for app/services/blend.py."""

import math
import unittest

from app.services.blend import blend


class BlendTest(unittest.TestCase):
    """Geometric mean fusion tests."""

    def test_empty_signals(self) -> None:
        """Empty list returns 0.0."""
        self.assertEqual(blend([]), 0.0)

    def test_single_signal(self) -> None:
        """Single signal returns (value + eps)."""
        result = blend([("kw", 0.5)])
        eps = 0.05
        expected = math.exp(math.log(0.5 + eps) / 1)
        self.assertAlmostEqual(result, expected)

    def test_two_signals(self) -> None:
        """Two signals compute geometric mean correctly."""
        result = blend([("a", 0.8), ("b", 0.6)])
        eps = 0.05
        log_sum = math.log(0.8 + eps) + math.log(0.6 + eps)
        expected = math.exp(log_sum / 2)
        self.assertAlmostEqual(result, expected)

    def test_zero_signal(self) -> None:
        """Signal with value 0 returns eps (0.05)."""
        result = blend([("x", 0.0)])
        self.assertAlmostEqual(result, 0.05)

    def test_all_equal(self) -> None:
        """All signals at 1.0 returns approximately 1.0."""
        result = blend([("a", 1.0), ("b", 1.0), ("c", 1.0)])
        expected = 1.0  # clamped to [0, 1]
        self.assertAlmostEqual(result, expected)

    def test_one_signal_zero(self) -> None:
        """One zero signal among many gives very low but non-zero score."""
        result = blend([("a", 1.0), ("b", 0.0), ("c", 1.0)])
        eps = 0.05
        log_sum = math.log(1.0 + eps) + math.log(0.0 + eps) + math.log(1.0 + eps)
        expected = math.exp(log_sum / 3)
        self.assertAlmostEqual(result, expected)

    def test_values_clamped(self) -> None:
        """Output is always in [0, 1]."""
        for val in [0.0, 0.1, 0.5, 0.9, 1.0]:
            r = blend([("x", val)])
            self.assertGreaterEqual(r, 0.0)
            self.assertLessEqual(r, 1.0)
        # Multiple signals
        r2 = blend([("a", 0.0), ("b", 0.0)])
        self.assertGreaterEqual(r2, 0.0)
        self.assertLessEqual(r2, 1.0)
        r3 = blend([("a", 1.0), ("b", 1.0)])
        self.assertGreaterEqual(r3, 0.0)
        self.assertLessEqual(r3, 1.0)
