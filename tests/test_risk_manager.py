"""
Unit tests for risk management system.
"""

import unittest
from datetime import datetime
from unittest.mock import Mock
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.risk_manager import RiskManager, RiskEventType
from src.api.broker_interface import AccountInfo, Position


class TestRiskManager(unittest.TestCase):
    """Test risk management system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.risk_manager = RiskManager(initial_capital=10000.0)
        
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
        """Test risk manager initialization."""
        self.assertEqual(self.risk_manager.initial_capital, 10000.0)
        self.assertEqual(self.risk_manager.daily_pnl, 0.0)
        self.assertEqual(self.risk_manager.weekly_pnl, 0.0)
        self.assertEqual(self.risk_manager.consecutive_losses, 0)
    
    def test_calculate_position_size(self):
        """Test position size calculation."""
        entry_price = 100.0
        position_size = self.risk_manager.calculate_position_size(
            self.account_info,
            entry_price
        )
        
        self.assertGreater(position_size, 0)
    
    def test_check_daily_loss_limit_not_reached(self):
        """Test daily loss limit when not reached."""
        self.risk_manager.daily_pnl = -100  # 1% loss
        
        limit_reached, loss_pct = self.risk_manager.check_daily_loss_limit(self.account_info)
        
        self.assertFalse(limit_reached)
        self.assertLess(loss_pct, 0.05)  # Less than 5%
    
    def test_check_daily_loss_limit_reached(self):
        """Test daily loss limit when reached."""
        self.risk_manager.daily_pnl = -600  # 6% loss (over 5% limit)
        
        limit_reached, loss_pct = self.risk_manager.check_daily_loss_limit(self.account_info)
        
        self.assertTrue(limit_reached)
        self.assertGreater(loss_pct, 0.05)
    
    def test_check_weekly_loss_limit_not_reached(self):
        """Test weekly loss limit when not reached."""
        self.risk_manager.weekly_pnl = -500  # 5% loss
        
        limit_reached, loss_pct = self.risk_manager.check_weekly_loss_limit(self.account_info)
        
        self.assertFalse(limit_reached)
        self.assertLess(loss_pct, 0.10)  # Less than 10%
    
    def test_check_weekly_loss_limit_reached(self):
        """Test weekly loss limit when reached."""
        self.risk_manager.weekly_pnl = -1200  # 12% loss (over 10% limit)
        
        limit_reached, loss_pct = self.risk_manager.check_weekly_loss_limit(self.account_info)
        
        self.assertTrue(limit_reached)
        self.assertGreater(loss_pct, 0.10)
    
    def test_check_max_positions_not_reached(self):
        """Test max positions when not reached."""
        positions = []
        
        limit_reached, count = self.risk_manager.check_max_positions(positions)
        
        self.assertFalse(limit_reached)
        self.assertEqual(count, 0)
    
    def test_check_max_positions_reached(self):
        """Test max positions when reached."""
        positions = [Mock(), Mock()]  # 2 positions (max is 2)
        
        limit_reached, count = self.risk_manager.check_max_positions(positions)
        
        self.assertTrue(limit_reached)
        self.assertEqual(count, 2)
    
    def test_check_cooldown_not_active(self):
        """Test cooldown when not active."""
        self.risk_manager.cooldown_trades_remaining = 0
        
        cooldown_active, remaining = self.risk_manager.check_cooldown()
        
        self.assertFalse(cooldown_active)
        self.assertEqual(remaining, 0)
    
    def test_check_cooldown_active(self):
        """Test cooldown when active."""
        self.risk_manager.cooldown_trades_remaining = 3
        
        cooldown_active, remaining = self.risk_manager.check_cooldown()
        
        self.assertTrue(cooldown_active)
        self.assertEqual(remaining, 3)
    
    def test_can_open_trade_all_pass(self):
        """Test can_open_trade when all checks pass."""
        positions = []
        
        can_open, reason = self.risk_manager.can_open_trade(
            self.account_info,
            positions,
            "XAUUSD"
        )
        
        self.assertTrue(can_open)
        self.assertEqual(reason, "All risk checks passed")
    
    def test_can_open_trade_daily_limit(self):
        """Test can_open_trade when daily limit reached."""
        self.risk_manager.daily_pnl = -600
        positions = []
        
        can_open, reason = self.risk_manager.can_open_trade(
            self.account_info,
            positions,
            "XAUUSD"
        )
        
        self.assertFalse(can_open)
        self.assertIn("Daily loss limit", reason)
    
    def test_record_trade_pnl_profit(self):
        """Test recording profitable trade."""
        initial_losses = self.risk_manager.consecutive_losses
        
        self.risk_manager.record_trade_pnl(100)
        
        self.assertEqual(self.risk_manager.daily_pnl, 100)
        self.assertEqual(self.risk_manager.weekly_pnl, 100)
        self.assertEqual(self.risk_manager.consecutive_losses, 0)
    
    def test_record_trade_pnl_loss(self):
        """Test recording losing trade."""
        self.risk_manager.record_trade_pnl(-100)
        
        self.assertEqual(self.risk_manager.daily_pnl, -100)
        self.assertEqual(self.risk_manager.weekly_pnl, -100)
        self.assertEqual(self.risk_manager.consecutive_losses, 1)
        self.assertEqual(self.risk_manager.cooldown_trades_remaining, 3)
    
    def test_update_cooldown(self):
        """Test cooldown update."""
        self.risk_manager.cooldown_trades_remaining = 3
        
        self.risk_manager.update_cooldown()
        
        self.assertEqual(self.risk_manager.cooldown_trades_remaining, 2)
    
    def test_get_trade_limits(self):
        """Test getting trade limits."""
        limits = self.risk_manager.get_trade_limits(self.account_info)
        
        self.assertIsNotNone(limits)
        self.assertEqual(limits.max_positions, 2)
        self.assertGreater(limits.daily_loss_limit, 0)
        self.assertGreater(limits.weekly_loss_limit, 0)
    
    def test_get_risk_summary(self):
        """Test getting risk summary."""
        summary = self.risk_manager.get_risk_summary(self.account_info)
        
        self.assertIn('capital', summary)
        self.assertIn('daily_pnl', summary)
        self.assertIn('weekly_pnl', summary)
        self.assertIn('consecutive_losses', summary)
        self.assertIn('max_positions', summary)
    
    def test_position_sizing_with_pip_value(self):
        """Test position sizing with pip value integration for different assets."""
        # Test EURUSD (4 decimal places)
        position_size_eur = self.risk_manager.calculate_position_size(
            account_info=self.account_info,
            entry_price=1.1000,
            asset="EURUSD"
        )
        self.assertGreater(position_size_eur, 0)
        
        # Test XAUUSD (1 decimal place)
        position_size_xau = self.risk_manager.calculate_position_size(
            account_info=self.account_info,
            entry_price=2000.0,
            asset="XAUUSD"
        )
        self.assertGreater(position_size_xau, 0)
        
        # Test USDJPY (2 decimal places)
        position_size_jpy = self.risk_manager.calculate_position_size(
            account_info=self.account_info,
            entry_price=150.00,
            asset="USDJPY"
        )
        self.assertGreater(position_size_jpy, 0)
        
        # Position sizes should differ due to pip value calculations
        # XAUUSD should be smaller due to larger pip size
        self.assertNotEqual(position_size_eur, position_size_xau)


if __name__ == '__main__':
    unittest.main()
