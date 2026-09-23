"""
Parity test for the vectorized detector pre-filter used by the backtester.

MarketAnalyzer.precompute_verdict_mask must return True on exactly the bars
where the per-bar detect_bad_luck_moment (with a bounded window) returns a
BadLuckMoment, so using the mask to skip detector calls never changes
backtest results.
"""

import unittest
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.helpers import generate_sample_data
from src.core.market_analyzer import MarketAnalyzer


class TestVerdictMaskParity(unittest.TestCase):
    """Mask == per-bar detector on photovoltaic fixture data."""

    def test_mask_matches_per_bar_detector(self):
        df = generate_sample_data(asset="XAUUSD", days=11, timeframe="M15", seed=3)
        analyzer = MarketAnalyzer()

        mask = analyzer.precompute_verdict_mask(df, "XAUUSD")

        per_bar = []
        for i in range(len(df)):
            window = df.iloc[max(0, i - 63):i + 1]
            moment = analyzer.detect_bad_luck_moment(window, "XAUUSD", window.index[-1])
            per_bar.append(moment is not None)

        mismatches = sum(1 for m, p in zip(mask.tolist(), per_bar) if bool(m) != p)
        self.assertEqual(mismatches, 0,
                         f"{mismatches} bars differ between mask and detector")


if __name__ == '__main__':
    unittest.main()