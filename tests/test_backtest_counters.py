"""
Regression tests for the diagnostic counters added to the Backtester
(signal/entry counts used by scripts/generate_backtest_report.py).
"""

import unittest
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.helpers import generate_sample_data


class TestBacktestCounters(unittest.TestCase):
    """Counters must be zeroed per run and reflect detector verdicts."""

    def _run_fixture(self):
        from backtesting.backtester import Backtester
        df = generate_sample_data(asset="XAUUSD", days=30, timeframe="M15", seed=7)
        bt = Backtester(initial_capital=10000.0)
        result = bt.run_backtest(df, "XAUUSD", df.index.min(), df.index.max())
        self.assertNotEqual(result.status.value, 'error', result.error_message)
        return bt, result

    def test_signal_count_incremented(self):
        """Raw detector verdicts before the randomness filter are counted."""
        bt, _ = self._run_fixture()
        self.assertGreaterEqual(bt._signal_count, 1)

    def test_entry_count_within_signals(self):
        """Entries (after the randomness filter) cannot exceed signals."""
        bt, _ = self._run_fixture()
        self.assertLessEqual(bt._entry_count, bt._signal_count)

    def test_signal_count_consistent_across_runs(self):
        """Raw verdicts are deterministic; entry counts vary by RNG by design."""
        from backtesting.backtester import Backtester
        df = generate_sample_data(asset="XAUUSD", days=30, timeframe="M15", seed=7)
        bt = Backtester(initial_capital=10000.0)
        bt.run_backtest(df, "XAUUSD", df.index.min(), df.index.max())
        s0 = bt._signal_count
        bt.run_backtest(df, "XAUUSD", df.index.min(), df.index.max())
        s1 = bt._signal_count
        self.assertGreaterEqual(s1, 1)
        self.assertEqual(s0, s1)

    def test_size_refusals_within_signals(self):
        """Lot-size refusals can never exceed raw signals."""
        bt, _ = self._run_fixture()
        self.assertLessEqual(bt._size_refusal_count, bt._signal_count)


if __name__ == '__main__':
    unittest.main()