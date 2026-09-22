"""
Regression tests for SHORT position PnL sign in both live execution
(trade_executor) and backtesting (backtester).

SHORT convention: profitable when price falls -> pnl = size * (entry - exit).
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import pytz

from src.core.trade_executor import TradeExecutor, Trade, TradeStatus
from src.api.broker_interface import AccountInfo
from config.strategy_params import TRADE_MANAGEMENT, RISK_MANAGEMENT, BAD_LUCK_DETECTOR, RANDOM_DECISION
from backtesting.backtester import Backtester


def build_ohlcv_df(entry_price, n=150, last_close=None):
    """Build a monotonically drifting OHLCV frame of n bars ending at entry_price."""
    step = 0.1
    closes = [entry_price - (n - i) * step for i in range(n)]
    if last_close is not None:
        closes[-1] = last_close
    df = pd.DataFrame({
        'open': [c - step for c in closes],
        'high': [c + step for c in closes],
        'low': [c - step for c in closes],
        'close': closes,
        'volume': [1000] * n,
    })
    now = datetime.now(pytz.UTC)
    df.index = pd.date_range(end=now, periods=n, freq='15min')
    return df


class TestShortPnlLiveExecution(unittest.TestCase):
    """SHORT PnL sign produced by trade_executor.close_trade."""

    def setUp(self):
        self.mock_broker = Mock()
        self.mock_risk_manager = Mock()
        self.executor = TradeExecutor(
            unified_broker=self.mock_broker,
            risk_manager=self.mock_risk_manager
        )
        self.account_info = AccountInfo(
            balance=10000, equity=10000, margin=0,
            free_margin=10000, margin_level=0,
            open_positions=0, total_trades=0
        )

    def _make_short_trade(self, entry_price, trade_id="SHORT001"):
        trade = Trade(
            trade_id=trade_id,
            asset="XAUUSD",
            direction="SHORT",
            entry_price=entry_price,
            size=1.0,
            stop_loss=entry_price * 1.02,
            take_profit=entry_price * 0.98,
            entry_time=datetime.now(pytz.UTC),
            status=TradeStatus.OPEN
        )
        self.executor.active_trades[trade_id] = trade
        self.mock_broker.get_broker_for_asset.return_value = self.mock_broker
        self.mock_broker.close_position.return_value = True
        return trade

    def test_short_profit_when_price_drops(self):
        """Short must report positive PnL when price falls below entry."""
        entry = 2000.0
        trade = self._make_short_trade(entry)
        exit_price = 1980.0

        self.assertTrue(self.executor.close_trade(trade, exit_price, "Take Profit"))

        expected_pnl = 1.0 * (entry - exit_price)
        self.assertAlmostEqual(trade.pnl, expected_pnl, places=6)
        self.assertGreater(trade.pnl, 0)
        self.assertGreater(trade.pnl_pct, 0)
        self.assertEqual(trade.status, TradeStatus.CLOSED)

    def test_short_loss_when_price_rises(self):
        """Short must report negative PnL when price rises above entry."""
        entry = 2000.0
        trade = self._make_short_trade(entry)
        exit_price = 2030.0

        self.assertTrue(self.executor.close_trade(trade, exit_price, "Stop Loss"))

        expected_pnl = 1.0 * (entry - exit_price)
        self.assertAlmostEqual(trade.pnl, expected_pnl, places=6)
        self.assertLess(trade.pnl, 0)
        self.assertLess(trade.pnl_pct, 0)
        self.assertEqual(trade.status, TradeStatus.CLOSED)


class ScriptedBacktester(Backtester):
    """Backtester whose single signal is scripted for deterministic SHORT tests."""

    def __init__(self, direction, entry_price, **kwargs):
        super().__init__(**kwargs)
        self.direction = direction
        self.entry_price = entry_price
        self.commission = 0.0
        self.slippage = 0.0
        self.trailing_stop = False
        self.trailing_activation_pct = 0.0
        self.max_duration_candles = 1000
        self._call_count = 0

    def _check_signal(self, data, asset, current_time):
        if self._call_count > 0:
            return None
        self._call_count += 1
        return {
            'signal_type': 'ENTRY',
            'direction': self.direction,
            'entry_price': self.entry_price,
            'confidence': 1.0,
            'asset': asset,
            'timeframe': 'M15',
            'timestamp': current_time
        }


class TestShortPnlBacktester(unittest.TestCase):
    """SHORT PnL sign produced by the backtester."""

    def test_short_take_profit_positive_pnl(self):
        """Short hitting take profit in backtest must produce positive PnL."""
        entry = 2000.0
        take_profit = entry * (1 - TRADE_MANAGEMENT['take_profit_pct'])
        # Bars fall below TP so the SHORT is filled at TP.
        df = build_ohlcv_df(entry, n=120, last_close=take_profit - 10)

        bt = ScriptedBacktester('SHORT', entry, initial_capital=10000.0)
        result = bt.run_backtest(
            df, "XAUUSD", df.index.min(), df.index.max()
        )

        self.assertEqual(result.status.value, 'completed')
        self.assertEqual(result.total_trades, 1)
        trade = result.trades[0]
        self.assertEqual(trade.direction, 'SHORT')
        self.assertIn(trade.exit_reason, ('Take Profit', 'MAX_DURATION_REACHED'))
        self.assertGreater(trade.pnl, 0)

    def test_short_stop_loss_negative_pnl(self):
        """Short stopped out in backtest must produce negative PnL."""
        entry = 2000.0
        stop_loss = entry * (1 + TRADE_MANAGEMENT['stop_loss_pct'])
        # Bars rise above SL so the SHORT is stopped out at SL.
        df = build_ohlcv_df(entry, n=120, last_close=stop_loss + 10)

        bt = ScriptedBacktester('SHORT', entry, initial_capital=10000.0)
        result = bt.run_backtest(
            df, "XAUUSD", df.index.min(), df.index.max()
        )

        self.assertEqual(result.status.value, 'completed')
        self.assertEqual(result.total_trades, 1)
        trade = result.trades[0]
        self.assertEqual(trade.direction, 'SHORT')
        self.assertIn(trade.exit_reason, ('Stop Loss', 'MAX_DURATION_REACHED'))
        self.assertLess(trade.pnl, 0)


if __name__ == '__main__':
    unittest.main()
