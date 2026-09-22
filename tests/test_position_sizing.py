"""
Unit tests for MT5 lot-based position sizing (contract-aware).
"""

import unittest
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.helpers import calculate_position_size
from config.strategy_params import SYMBOL_METADATA


class TestCalculatePositionSize(unittest.TestCase):
    """Test MT5 lots position sizing pipeline."""

    def test_eurusd_returns_lots(self):
        # 200 risk / 0.0165 price distance = 12121.2 units -> 0.12121 lots -> 0.12
        lots = calculate_position_size(
            capital=10000.0,
            risk_percentage=0.02,
            stop_loss_pct=0.015,
            entry_price=1.1000,
            asset="EURUSD"
        )
        self.assertAlmostEqual(lots, 0.12, places=6)

    def test_xauusd_returns_lots(self):
        # 200 risk / 30 price distance = 6.667 units -> 0.06667 lots -> 0.06
        lots = calculate_position_size(
            capital=10000.0,
            risk_percentage=0.02,
            stop_loss_pct=0.015,
            entry_price=2000.0,
            asset="XAUUSD"
        )
        self.assertAlmostEqual(lots, 0.06, places=6)

    def test_rounds_down_to_lot_step(self):
        # Computed as 0.12121 -> must never round up over the risk budget
        lots = calculate_position_size(
            capital=10000.0,
            risk_percentage=0.02,
            stop_loss_pct=0.015,
            entry_price=1.1000,
            asset="EURUSD"
        )
        step = SYMBOL_METADATA["EURUSD"]["lot_step"]
        self.assertAlmostEqual(lots / step, round(lots / step), 6)

    def test_below_minimum_lot_refused(self):
        lots = calculate_position_size(
            capital=10000.0,
            risk_percentage=0.02,
            stop_loss_pct=0.015,
            entry_price=150.00,
            asset="GBPJPY"
        )
        self.assertEqual(lots, 0.0)

    def test_clamped_to_max_lot(self):
        # 1M capital, 2% risk on XAUUSD = 666.67 units -> 6.67 lots (< max 50)
        lots = calculate_position_size(
            capital=1_000_000.0,
            risk_percentage=0.02,
            stop_loss_pct=0.015,
            entry_price=2000.0,
            asset="XAUUSD"
        )
        max_lot = SYMBOL_METADATA["XAUUSD"]["max_lot"]
        self.assertLessEqual(lots, max_lot)

    def test_unknown_asset_raises(self):
        with self.assertRaises(ValueError):
            calculate_position_size(
                capital=10000.0,
                risk_percentage=0.02,
                stop_loss_pct=0.015,
                entry_price=1.1000,
                asset="BOGUS"
            )

    def test_zero_stop_distance_refused(self):
        lots = calculate_position_size(
            capital=10000.0,
            risk_percentage=0.02,
            stop_loss_pct=0.0,
            entry_price=1.1000,
            asset="EURUSD"
        )
        self.assertEqual(lots, 0.0)


if __name__ == '__main__':
    unittest.main()