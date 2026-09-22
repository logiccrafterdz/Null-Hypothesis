"""
Unit tests for trade execution.
"""

import unittest
from datetime import datetime
from unittest.mock import Mock, MagicMock
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.trade_executor import TradeExecutor, TradeStatus
from src.api.broker_interface import AccountInfo, Position


class TestTradeExecutor(unittest.TestCase):
    """Test trade execution system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_broker = Mock()
        self.mock_risk_manager = Mock()
        
        self.trade_executor = TradeExecutor(
            unified_broker=self.mock_broker,
            risk_manager=self.mock_risk_manager
        )
        
        self.account_info = AccountInfo(
            balance=10000,
            equity=10000,
            margin=0,
            free_margin=10000,
            margin_level=0,
            open_positions=0,
            total_trades=0
        )
    
    def test_initialization(self):
        """Test trade executor initialization."""
        self.assertIsNotNone(self.trade_executor.risk_manager)
        self.assertIsNotNone(self.trade_executor.unified_broker)
        self.assertEqual(len(self.trade_executor.active_trades), 0)
        self.assertEqual(len(self.trade_executor.trade_history), 0)
    
    def test_calculate_stop_loss_long(self):
        """Test stop loss calculation for long position."""
        entry_price = 100.0
        stop_loss = self.trade_executor.calculate_stop_loss(entry_price, 'LONG')
        
        self.assertLess(stop_loss, entry_price)
        expected_sl = entry_price * (1 - self.trade_executor.stop_loss_pct)
        self.assertAlmostEqual(stop_loss, expected_sl, places=2)
    
    def test_calculate_stop_loss_short(self):
        """Test stop loss calculation for short position."""
        entry_price = 100.0
        stop_loss = self.trade_executor.calculate_stop_loss(entry_price, 'SHORT')
        
        self.assertGreater(stop_loss, entry_price)
        expected_sl = entry_price * (1 + self.trade_executor.stop_loss_pct)
        self.assertAlmostEqual(stop_loss, expected_sl, places=2)
    
    def test_calculate_take_profit_long(self):
        """Test take profit calculation for long position."""
        entry_price = 100.0
        take_profit = self.trade_executor.calculate_take_profit(entry_price, 'LONG')
        
        self.assertGreater(take_profit, entry_price)
        expected_tp = entry_price * (1 + self.trade_executor.take_profit_pct)
        self.assertAlmostEqual(take_profit, expected_tp, places=2)
    
    def test_calculate_take_profit_short(self):
        """Test take profit calculation for short position."""
        entry_price = 100.0
        take_profit = self.trade_executor.calculate_take_profit(entry_price, 'SHORT')
        
        self.assertLess(take_profit, entry_price)
        expected_tp = entry_price * (1 - self.trade_executor.take_profit_pct)
        self.assertAlmostEqual(take_profit, expected_tp, places=2)
    
    def test_determine_direction(self):
        """Test trade direction determination."""
        market_conditions = {}
        direction = self.trade_executor.determine_direction(market_conditions)
        
        self.assertIn(direction, ['LONG', 'SHORT'])
    
    def test_execute_trade_no_broker(self):
        """Test trade execution when no broker is available."""
        self.mock_broker.get_broker_for_asset.return_value = None
        
        trade = self.trade_executor.execute_trade(
            asset="XAUUSD",
            account_info=self.account_info,
            current_price=100.0,
            market_conditions={}
        )
        
        self.assertIsNone(trade)
    
    def test_execute_trade_success(self):
        """Test successful trade execution."""
        # Mock broker
        mock_broker = Mock()
        mock_broker.place_order.return_value = "ORDER123"
        self.mock_broker.get_broker_for_asset.return_value = mock_broker
        
        # Mock risk manager
        self.mock_risk_manager.calculate_position_size.return_value = 1.0
        
        trade = self.trade_executor.execute_trade(
            asset="XAUUSD",
            account_info=self.account_info,
            current_price=100.0,
            market_conditions={}
        )
        
        # Trade should be created with the order id as canonical identifier
        self.assertIsNotNone(trade)
        self.assertEqual(trade.trade_id, "ORDER123")
        self.assertIn("ORDER123", self.trade_executor.active_trades)
        self.assertEqual(self.trade_executor.active_trades["ORDER123"], trade)
        self.assertEqual(trade.asset, "XAUUSD")
        self.assertEqual(trade.direction, 'LONG')
        self.assertEqual(trade.entry_price, 100.0)
        self.assertEqual(trade.size, 1.0)
    
    def test_get_active_trades_empty(self):
        """Test getting active trades when none exist."""
        trades = self.trade_executor.get_active_trades()
        
        self.assertEqual(len(trades), 0)
    
    def test_get_trade_history_empty(self):
        """Test getting trade history when none exist."""
        history = self.trade_executor.get_trade_history()
        
        self.assertEqual(len(history), 0)
    
    def test_get_trade_statistics_empty(self):
        """Test getting trade statistics when no trades exist."""
        stats = self.trade_executor.get_trade_statistics()
        
        self.assertEqual(stats['total_trades'], 0)
        self.assertEqual(stats['win_rate'], 0.0)
        self.assertEqual(stats['profit_factor'], 0.0)
    
    def test_close_all_trades_empty(self):
        """Test closing all trades when none exist."""
        closed_count = self.trade_executor.close_all_trades()
        
        self.assertEqual(closed_count, 0)
    
    def test_max_duration_enforcement(self):
        """Test that trades are closed after max duration."""
        from src.core.trade_executor import Trade, TradeStatus
        from datetime import datetime, timedelta
        import pytz
        
        # Create a mock trade
        mock_trade = Trade(
            trade_id="TEST001",
            asset="XAUUSD",
            direction="LONG",
            entry_price=100.0,
            size=1.0,
            stop_loss=98.5,
            take_profit=103.0,
            entry_time=datetime.now(pytz.UTC),
            status=TradeStatus.OPEN
        )
        
        # Add to active trades
        self.trade_executor.active_trades["TEST001"] = mock_trade
        
        # Mock broker
        mock_broker = Mock()
        mock_broker.get_current_price.return_value = 101.0
        self.mock_broker.get_broker_for_asset.return_value = mock_broker
        
        # Simulate monitoring for max_duration_candles cycles
        trades_to_close = []
        for i in range(self.trade_executor.max_duration_candles + 1):
            trades_to_close = self.trade_executor.monitor_positions()
        
        # Check if trade was closed for max duration
        max_duration_triggered = any(
            reason == "MAX_DURATION_REACHED" 
            for _, reason in trades_to_close
        )
        
        self.assertTrue(max_duration_triggered, "Trade should be closed after max duration")
        self.assertEqual(mock_trade.candles_since_entry, self.trade_executor.max_duration_candles + 1)


if __name__ == '__main__':
    unittest.main()
