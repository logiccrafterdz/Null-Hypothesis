"""
Regression tests for backtester exit execution.
Verifies SL/TP/trailing/max-duration closes actually remove positions,
record correct reasons and PnL, and update equity/capital correctly.
"""

import unittest
from datetime import datetime
import sys
from pathlib import Path

import pandas as pd
import pytz

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtesting.backtester import Backtester, BacktestResult


def build_ohlcv_df(closes, lows=None, highs=None):
    """Build a synthetic OHLCV DataFrame around the given closes."""
    n = len(closes)
    if lows is None:
        lows = [c - 0.2 for c in closes]
    if highs is None:
        highs = [c + 0.2 for c in closes]
    opens = [c - 0.1 for c in closes]
    volumes = [1000] * n
    index = pd.date_range(
        start=datetime(2024, 1, 2, 12, 0, tzinfo=pytz.UTC),
        periods=n,
        freq='15min'
    )
    return pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes,
    }, index=index)


class ScriptedBacktester(Backtester):
    """Backtester whose signal generation is scripted for deterministic tests."""

    def __init__(self, signal_len=5, **kwargs):
        super().__init__(**kwargs)
        self.signal_len = signal_len

    def _check_signal(self, data, asset, current_time):
        if len(data) == self.signal_len:
            return {
                'direction': 'LONG',
                'entry_price': data['close'].iloc[-1],
                'confidence': 1.0,
            }
        return None


class TestBacktestExitExecution(unittest.TestCase):
    """Test that backtester closes trades on exit conditions."""

    def _run_with_close(self, closes, lows=None, highs=None, max_duration=None):
        df = build_ohlcv_df(closes, lows, highs)
        backtester = ScriptedBacktester()
        if max_duration is not None:
            backtester.max_duration_candles = max_duration
        return backtester.run_backtest(
            df,
            "XAUUSD",
            df.index.min(),
            df.index.max()
        )

    def test_stop_loss_close(self):
        """A LONG trade whose bar low pierces the stop loss closes as Stop Loss."""
        closes = [100.0] * 110
        lows = [99.8] * 110
        highs = [100.2] * 110
        lows[5] = 97.0
        closes[5] = 98.0

        result = self._run_with_close(closes, lows, highs)

        self.assertEqual(result.status.value, 'completed')
        self.assertEqual(result.total_trades, 1)
        trade = result.trades[0]
        self.assertEqual(trade.direction, 'LONG')
        self.assertEqual(trade.exit_reason, 'Stop Loss')
        self.assertLess(trade.pnl, 0)
        self.assertLess(result.final_capital, result.initial_capital)
        self.assertEqual(len(result.equity_curve), 110)

    def test_take_profit_close(self):
        """A LONG trade whose bar high reaches take profit closes as Take Profit."""
        closes = [100.0] * 110
        lows = [99.8] * 110
        highs = [100.2] * 110
        closes[5] = 103.5
        highs[5] = 104.0
        lows[5] = 103.2

        result = self._run_with_close(closes, lows, highs)

        self.assertEqual(result.total_trades, 1)
        trade = result.trades[0]
        self.assertEqual(trade.exit_reason, 'Take Profit')
        self.assertGreater(trade.pnl, 0)
        self.assertGreater(result.final_capital, result.initial_capital)

    def test_trailing_stop_close(self):
        """Trailing stop activates after profit threshold, then price pulls back."""
        closes = [100.0] * 110
        lows = [99.8] * 110
        highs = [100.2] * 110
        closes[5] = 102.0
        highs[5] = 102.5
        lows[5] = 101.0

        result = self._run_with_close(closes, lows, highs)

        self.assertEqual(result.total_trades, 1)
        trade = result.trades[0]
        self.assertEqual(trade.exit_reason, 'Trailing Stop')
        self.assertGreater(trade.pnl, 0)

    def test_max_duration_close(self):
        """Trade that never hits SL/TP closes after max duration candles."""
        closes = [100.0] * 110
        lows = [99.8] * 110
        highs = [100.2] * 110

        # Entry at bar 4, bars_held reaches max_duration_candles at bar 4+15
        result = self._run_with_close(closes, lows, highs)

        self.assertEqual(result.total_trades, 1)
        trade = result.trades[0]
        self.assertEqual(trade.exit_reason, 'MAX_DURATION_REACHED')

    def test_no_exit_trade_stays_open(self):
        """Trade with no triggers stays open until end of backtest."""
        closes = [100.0] * 110
        lows = [99.8] * 110
        highs = [100.2] * 110

        df = build_ohlcv_df(closes, lows, highs)
        backtester = ScriptedBacktester()
        backtester.max_duration_candles = 1000
        result = backtester.run_backtest(
            df,
            "XAUUSD",
            df.index.min(),
            df.index.max(),
        )

        self.assertEqual(result.total_trades, 1)
        trade = result.trades[0]
        self.assertEqual(trade.exit_reason, 'End of Backtest')

    def test_remaining_positions_count(self):
        """Closed trades are removed from the open set."""
        closes = [100.0] * 110
        lows = [99.8] * 110
        highs = [100.2] * 110
        lows[5] = 97.0
        closes[5] = 98.0

        df = build_ohlcv_df(closes, lows, highs)
        backtester = ScriptedBacktester()
        result = backtester.run_backtest(df, "XAUUSD", df.index.min(), df.index.max())

        self.assertEqual(result.total_trades, 1)
        self.assertEqual(result.status.value, 'completed')


if __name__ == '__main__':
    unittest.main()