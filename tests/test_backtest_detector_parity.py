"""
Regression tests ensuring the backtester uses the production bird luck
moment detector configuration (drop >= 3%, volume >= 2x, ATR >= 1.5x and
reversal patterns) instead of the old hardcoded simplified thresholds.
"""

import unittest
from datetime import datetime
import sys
from pathlib import Path

import pandas as pd
import pytz

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtesting.backtester import Backtester
from src.core.market_analyzer import MarketAnalyzer


def build_capitulation_data(drop_close, n=130):
    """
    Build synthetic data whose final bar is a capitulation candle (doji/hammer
    with a large range), a volume spike and an ATR spike, with the requested
    close to control the price drop percentage.
    """
    closes = [103.0 - 0.03 * i for i in range(n)]
    closes[128] = 99.0
    closes[129] = drop_close

    opens = [c - 0.1 for c in closes]
    highs = [c + 0.4 for c in closes]
    lows = [c - 0.4 for c in closes]

    opens[129] = drop_close + 0.2
    highs[129] = drop_close + 0.4
    lows[129] = drop_close - 7.0

    volumes = [1000] * n
    volumes[129] = 3000

    index = pd.date_range(
        start=datetime(2024, 1, 1, 12, 0, tzinfo=pytz.UTC),
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


def build_flat_data(n=130):
    """Build synthetic calm data with no capitulation conditions."""
    closes = [103.0 - 0.03 * i for i in range(n)]
    opens = [c - 0.1 for c in closes]
    highs = [c + 0.4 for c in closes]
    lows = [c - 0.4 for c in closes]
    volumes = [1000] * n

    index = pd.date_range(
        start=datetime(2024, 1, 1, 12, 0, tzinfo=pytz.UTC),
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


class TestBacktestUsesProductionDetector(unittest.TestCase):
    """Backtest signal detection must match production configuration."""

    def test_trigger_when_all_production_conditions_met(self):
        """A 4% drop with volume spike, ATR spike and reversal pattern produces a trade."""
        df = build_capitulation_data(drop_close=95.0)

        backtester = Backtester()
        backtester.decision_engine.adjust_entry_probability(1.0)

        result = backtester.run_backtest(df, "XAUUSD", df.index.min(), df.index.max())

        self.assertEqual(result.status.value, 'completed')
        self.assertEqual(result.total_trades, 1)
        trade = result.trades[0]
        self.assertEqual(trade.direction, 'LONG')
        self.assertEqual(trade.entry_price, 95.0 * (1 + backtester.slippage))

    def test_drop_below_3_percent_does_not_trigger(self):
        """A 2.5% drop must NOT trigger (production threshold is 3%, not 2%)."""
        df = build_capitulation_data(drop_close=96.5)

        backtester = Backtester()
        backtester.decision_engine.adjust_entry_probability(1.0)

        result = backtester.run_backtest(df, "XAUUSD", df.index.min(), df.index.max())

        self.assertEqual(result.status.value, 'completed')
        self.assertEqual(result.total_trades, 0)

    def test_no_trigger_on_normal_market(self):
        """Calm market with flat volume and no big drop produces no trades."""
        df = build_flat_data()

        backtester = Backtester()
        backtester.decision_engine.adjust_entry_probability(1.0)

        result = backtester.run_backtest(df, "XAUUSD", df.index.min(), df.index.max())

        self.assertEqual(result.status.value, 'completed')
        self.assertEqual(result.total_trades, 0)

    def test_detector_parity_with_standalone_analyzer(self):
        """Backtester uses the same MarketAnalyzer as live trading."""
        trigger_df = build_capitulation_data(drop_close=95.0)
        sub_threshold_df = build_capitulation_data(drop_close=96.5)

        analyzer = MarketAnalyzer()
        moment = analyzer.detect_bad_luck_moment(
            trigger_df, "XAUUSD", trigger_df.index[-1]
        )
        self.assertIsNotNone(moment)
        self.assertTrue(moment.conditions['price_drop_met'])
        self.assertTrue(moment.conditions['volume_spike_met'])
        self.assertTrue(moment.conditions['volatility_spike_met'])
        self.assertTrue(moment.conditions['reversal_pattern_met'])

        no_moment = analyzer.detect_bad_luck_moment(
            sub_threshold_df, "XAUUSD", sub_threshold_df.index[-1]
        )
        self.assertIsNone(no_moment)


if __name__ == '__main__':
    unittest.main()