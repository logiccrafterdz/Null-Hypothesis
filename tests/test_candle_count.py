"""
Regression tests for candle-count consistency between live data fetch
and the backtest warmup guard.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import pytz

from src.core.data_fetcher import DataFetcher
from config.strategy_params import BAD_LUCK_DETECTOR


class TestLatestDataCandleCount(unittest.TestCase):
    """get_latest_data must reliably return the requested number of candles."""

    def setUp(self):
        self.mock_broker = Mock()
        self.fetcher = DataFetcher(self.mock_broker)

    def _make_frame(self, n):
        index = pd.date_range(
            end=datetime.now(pytz.UTC), periods=n, freq='15min', tz=pytz.UTC
        )
        return pd.DataFrame({
            'open': 100.0, 'high': 101.0, 'low': 99.0,
            'close': 100.5, 'volume': 1000,
        }, index=index)

    def test_returns_exactly_requested_candles(self):
        """With a cache containing more candles than requested, tail must
        hand back exactly num_candles rows."""
        with patch.object(self.fetcher, 'get_data', return_value=self._make_frame(150)):
            result = self.fetcher.get_latest_data("XAUUSD", "M15", num_candles=100)
        self.assertEqual(len(result), 100)

    def test_window_has_margin_for_filtering(self):
        """The requested window must exceed num_candles worth of minutes so
        the date-range filter does not drop candles at the start boundary."""
        captured = {}

        def fake_get_data(symbol, timeframe, start_date, end_date):
            captured['start'] = start_date
            captured['end'] = end_date
            return self._make_frame(150)

        with patch.object(self.fetcher, 'get_data', side_effect=fake_get_data):
            self.fetcher.get_latest_data("XAUUSD", "M15", num_candles=100)

        window_minutes = (captured['end'] - captured['start']).total_seconds() / 60
        self.assertGreater(window_minutes, 15 * 100)


class TestBacktestWarmupGuard(unittest.TestCase):
    """The backtester warmup guard must use the configuration-driven minimum."""

    def test_warmup_bars_configured(self):
        self.assertGreaterEqual(BAD_LUCK_DETECTOR['warmup_bars'], 20)
        self.assertLessEqual(BAD_LUCK_DETECTOR['warmup_bars'], 60)

    def test_backtest_rejects_below_warmup(self):
        from backtesting.backtester import Backtester
        bt = Backtester(initial_capital=10000.0)
        index = pd.date_range(
            start=datetime(2024, 1, 2, tzinfo=pytz.UTC),
            periods=BAD_LUCK_DETECTOR['warmup_bars'] - 1,
            freq='15min'
        )
        df = pd.DataFrame({
            'open': 100.0, 'high': 101.0, 'low': 99.0,
            'close': 100.5, 'volume': 1000,
        }, index=index)
        result = bt.run_backtest(
            df, "XAUUSD", index.min(), index.max()
        )
        self.assertEqual(result.status.value, 'error')
        self.assertIn("Insufficient data", result.error_message)


if __name__ == '__main__':
    unittest.main()