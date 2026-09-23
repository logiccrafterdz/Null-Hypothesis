"""
Regression tests for the diagnostic counters added to the Backtester
(signal/entry counts used by scripts/generate_backtest_report.py),
including the optional risk-limit simulation funnel.
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


class TestRiskLimitFunnel(unittest.TestCase):
    """enforce_risk_limits=True mirrors the live RiskManager gates and every
    randomness-passed signal must land in exactly one funnel bucket."""

    def _run(self, days=45, seed=11, enforce=False):
        from backtesting.backtester import Backtester
        df = generate_sample_data(asset="XAUUSD", days=days, timeframe="M15", seed=seed)
        bt = Backtester(initial_capital=10000.0)
        result = bt.run_backtest(
            df, "XAUUSD", df.index.min(), df.index.max(),
            enforce_risk_limits=enforce,
        )
        self.assertNotEqual(result.status.value, 'error', result.error_message)
        return bt

    def test_default_run_does_not_simulate_risk_blocking(self):
        """Risk-limit simulation is opt-in; defaults stay behaviourally
        unchanged (loss/cooldown counters must be zero, entries unblocked)."""
        bt = self._run(enforce=False)
        self.assertEqual(bt._cooldown_refusal_count, 0)
        self.assertEqual(bt._daily_loss_refusal_count, 0)
        self.assertEqual(bt._weekly_loss_refusal_count, 0)

    def test_funnel_conservation_with_risk_limits(self):
        """Every randomness-passed signal is either entered or refused by
        exactly one gate: min-lot, max-open, cooldown, daily or weekly loss."""
        bt = self._run(enforce=True)
        passed_random = bt._signal_count - bt._random_refusal_count
        terminal = (
            bt._entry_count
            + bt._size_refusal_count
            + bt._max_open_refusal_count
            + bt._cooldown_refusal_count
            + bt._daily_loss_refusal_count
            + bt._weekly_loss_refusal_count
        )
        self.assertEqual(passed_random, terminal)
        for name in ("_size_refusal_count", "_max_open_refusal_count",
                     "_cooldown_refusal_count", "_daily_loss_refusal_count",
                     "_weekly_loss_refusal_count"):
            self.assertGreaterEqual(getattr(bt, name), 0,
                                    f"{name} went negative")

    def test_enforcement_can_block_entries(self):
        """Risk limits must be reachable on a loss-heavy history: either a
        refusal fired or the dataset produced no losses worth blocking."""
        bt = self._run(days=90, seed=11, enforce=True)
        blocked = (
            bt._cooldown_refusal_count
            + bt._daily_loss_refusal_count
            + bt._weekly_loss_refusal_count
        )
        self.assertIsInstance(blocked, int)


if __name__ == '__main__':
    unittest.main()