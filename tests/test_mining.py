"""
Unit tests for the mining platform (Chaos Discovery Engine).

Covers the condition library, the random strategy generator, the statistical
filters and the robustness helpers. These tests are fast and synthetic; the
reference reproduction against real Phase-8 data is exercised by
scripts/run_mining_session.py --validate-only.
"""

import unittest
import sys
from pathlib import Path

import numpy as np
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mining.condition_library import (  # noqa: E402
    CONDITION_TEMPLATES,
    build_features,
    describe,
    evaluate_condition,
    evaluate_operator,
)
from src.mining.strategy_generator import StrategyGenerator  # noqa: E402
from src.mining.statistical_filters import (  # noqa: E402
    benjamini_hochberg,
    composite_score,
    p_value_of,
    passes_primary,
)


def make_df(n=600, seed=7, freq="15T"):
    """Deterministic synthetic OHLCV frame with a UTC DatetimeIndex."""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.05, n))
    open_ = 100 + np.cumsum(rng.normal(0, 0.05, n)) + rng.normal(0, 0.01, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.02, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.02, n))
    vol = rng.integers(100, 500, n).astype(float)
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": vol}, index=idx)


class TestConditionLibrary(unittest.TestCase):
    def test_more_than_50_condition_types(self):
        self.assertGreaterEqual(len(CONDITION_TEMPLATES), 50)

    def test_known_condition_masks(self):
        df = make_df()
        F = build_features(df)
        drop = evaluate_condition(F, {"type": "drop_gt", "params": {"x": 0.2}})
        self.assertEqual(len(drop), len(df))
        expect = df["close"].values < np.roll(df["close"].values, 1) * 0.998
        expect[0] = False
        np.testing.assert_array_equal(drop, expect)

        bull = evaluate_condition(F, {"type": "bull_candle", "params": {}})
        np.testing.assert_array_equal(
            bull, (df["close"] > df["open"]).values)

    def test_operator_and_or(self):
        F = build_features(make_df())
        bull = evaluate_condition(F, {"type": "bull_candle", "params": {}})
        bear = evaluate_condition(F, {"type": "bear_candle", "params": {}})
        cand = [{"type": "bull_candle", "params": {}},
                {"type": "bear_candle", "params": {}}]
        np.testing.assert_array_equal(
            evaluate_operator(F, cand, "or"), bull | bear)
        np.testing.assert_array_equal(
            evaluate_operator(F, cand, "and"), bull & bear)

    def test_describe(self):
        self.assertIn("0.2",
                      describe({"type": "drop_gt", "params": {"x": 0.2}}))


class TestStrategyGenerator(unittest.TestCase):
    def test_deterministic_sequence(self):
        a = StrategyGenerator(seed=42).generate_sequence("XAUUSD", 20)
        b = StrategyGenerator(seed=42).generate_sequence("XAUUSD", 20)
        self.assertEqual(a, b)

    def test_spec_shape(self):
        spec = StrategyGenerator(seed=1).generate("EURUSD")
        self.assertEqual(spec["asset"], "EURUSD")
        conditions = spec["entry"]["conditions"]
        self.assertGreaterEqual(len(conditions), 2)
        self.assertLessEqual(len(conditions), 5)
        self.assertIn(spec["direction"], ("LONG", "SHORT"))

    def test_random_entry_control(self):
        spec = StrategyGenerator(seed=3).generate_random_entry(
            "XAUUSD", density=0.01)
        self.assertEqual(spec["entry"]["operator"], "random")
        self.assertEqual(spec["entry"]["density"], 0.01)


class TestStatisticalFilters(unittest.TestCase):
    def test_primary_filter_accepts_only_good(self):
        good = {
            "total_trades": 200, "winrate": 0.52, "profit_factor": 1.5,
            "total_return_pct": 0.15, "max_dd_pct": 0.18,
            "expectancy": 7.0,
            "years": {2024: {"n": 90, "winrate": 0.48, "pf": 1.1,
                             "return_pct": 0.05},
                      2025: {"n": 110, "winrate": 0.47, "pf": 1.05,
                             "return_pct": 0.03}},
        }
        self.assertTrue(passes_primary(good))

    def test_primary_filter_rejects_drawdown(self):
        bad = {
            "total_trades": 200, "winrate": 0.52, "profit_factor": 1.5,
            "total_return_pct": 0.15, "max_dd_pct": 0.30,
            "expectancy": 7.0,
            "years": {2024: {"n": 90, "winrate": 0.48, "pf": 1.1,
                             "return_pct": 0.05}},
        }
        self.assertFalse(passes_primary(bad))

    def test_p_value_bound(self):
        # The empirical fraction is floored at 1/(N+1) - never a hard zero -
        # so a strategy ahead of the whole baseline still gets a small p.
        self.assertEqual(p_value_of(0.5, [0.1, 0.2, 0.3]),
                         1.0 / (3 + 1))
        self.assertEqual(p_value_of(-1.0, [0.1, 0.2, 0.3]), 1.0)

    def test_benjamini_hochberg(self):
        # All p-values tiny: everyone survives.
        keep = benjamini_hochberg([0.001, 0.002, 0.003], q=0.05)
        self.assertEqual(sorted(keep), [0, 1, 2])
        # A large p should not survive.
        keep = benjamini_hochberg([0.9, 0.001, 0.002], q=0.05)
        self.assertNotIn(0, keep)

    def test_composite_score_monotonic(self):
        base = {
            "profit_factor": 1.5, "winrate": 0.5, "sharpe": 1.0,
            "total_return_pct": 0.15, "max_dd_pct": 0.10,
        }
        better = dict(base, profit_factor=2.0)
        self.assertGreater(composite_score(better, 0.05, 0.0),
                           composite_score(base, 0.05, 0.0))


if __name__ == "__main__":
    unittest.main()