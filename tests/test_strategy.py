"""
Unit tests for trading strategy.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.strategies.bad_luck_strategy import BadLuckStrategy
from src.api.broker_interface import AccountInfo
from src.core.decision_engine import DecisionEngine
from config.strategy_params import RANDOM_DECISION


class TestBadLuckStrategy(unittest.TestCase):
    """Test Bad Luck Moment strategy."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock components
        self.mock_broker = Mock()
        self.mock_data_fetcher = Mock()
        self.mock_risk_manager = Mock()
        self.mock_trade_executor = Mock()
        
        # Create strategy
        self.strategy = BadLuckStrategy(
            unified_broker=self.mock_broker,
            data_fetcher=self.mock_data_fetcher,
            risk_manager=self.mock_risk_manager,
            trade_executor=self.mock_trade_executor
        )
        
        # Create sample data
        np.random.seed(42)
        dates = pd.date_range(start=datetime.now() - timedelta(days=100), periods=100, freq='15min')
        close_prices = 100 + np.cumsum(np.random.normal(0, 0.5, 100))
        
        self.sample_df = pd.DataFrame({
            'open': close_prices + np.random.uniform(-0.5, 0.5, 100),
            'high': close_prices + np.random.uniform(0, 1, 100),
            'low': close_prices - np.random.uniform(0, 1, 100),
            'close': close_prices,
            'volume': np.random.uniform(1000, 5000, 100)
        }, index=dates)
    
    def test_strategy_initialization(self):
        """Test strategy initialization."""
        self.assertEqual(self.strategy.name, "Bad Luck Moment")
        self.assertIsNotNone(self.strategy.market_analyzer)
        self.assertIsNotNone(self.strategy.decision_engine)
        self.assertTrue(self.strategy.is_enabled())
    
    def test_analyze_market_no_data(self):
        """Test market analysis with no data."""
        self.mock_data_fetcher.get_latest_data.return_value = pd.DataFrame()
        
        analysis = self.strategy.analyze_market("XAUUSD", "M15")
        
        self.assertEqual(analysis, {})
    
    def test_analyze_market_with_data(self):
        """Test market analysis with data."""
        self.mock_data_fetcher.get_latest_data.return_value = self.sample_df
        
        analysis = self.strategy.analyze_market("XAUUSD", "M15")
        
        self.assertIn('asset', analysis)
        self.assertIn('timeframe', analysis)
        self.assertEqual(analysis['asset'], "XAUUSD")
        self.assertEqual(analysis['timeframe'], "M15")
    
    def test_generate_signal_no_analysis(self):
        """Test signal generation with no analysis."""
        signal = self.strategy.generate_signal({})
        
        self.assertIsNone(signal)
    
    def test_generate_signal_no_signal(self):
        """Test signal generation when no signal is present."""
        analysis = {
            'has_signal': False,
            'asset': 'XAUUSD'
        }
        
        signal = self.strategy.generate_signal(analysis)
        
        self.assertIsNone(signal)
    
    def test_generate_signal_with_signal(self):
        """Test signal generation when signal is present."""
        # Create mock bad luck moment
        from src.core.market_analyzer import BadLuckMoment
        
        bad_luck_moment = BadLuckMoment(
            asset='XAUUSD',
            timestamp=datetime.now(),
            conditions={'price_drop': 0.05},
            accepted=False
        )
        
        analysis = {
            'has_signal': True,
            'bad_luck_moment': bad_luck_moment,
            'trend_filter_pass': True,
            'volatility_filter_pass': True,
            'data': self.sample_df,
            'asset': 'XAUUSD'
        }
        
        # Mock the decision engine to accept the trade
        self.strategy.decision_engine.decide_on_bad_luck_moment = Mock(return_value=(True, 0.5))
        
        signal = self.strategy.generate_signal(analysis)
        
        self.assertIsNotNone(signal)
        self.assertIn('asset', signal)
        self.assertIn('signal_type', signal)
        self.assertEqual(signal['asset'], 'XAUUSD')
        self.assertEqual(signal['signal_type'], 'ENTRY')
    
    def test_execute_signal_risk_blocked(self):
        """Test signal execution when blocked by risk management."""
        signal = {
            'asset': 'XAUUSD',
            'entry_price': 100.0,
            'direction': 'LONG'
        }
        
        account_info = AccountInfo(
            balance=10000,
            equity=10000,
            margin=0,
            free_margin=10000,
            margin_level=0,
            open_positions=0,
            total_trades=0
        )
        
        # Mock risk manager to block trade
        self.mock_risk_manager.can_open_trade.return_value = (False, "Daily limit reached")
        
        result = self.strategy.execute_signal(signal, account_info)
        
        self.assertFalse(result)
        self.mock_risk_manager.can_open_trade.assert_called_once()
    
    def test_execute_signal_success(self):
        """Test successful signal execution."""
        signal = {
            'asset': 'XAUUSD',
            'entry_price': 100.0,
            'direction': 'LONG'
        }
        
        account_info = AccountInfo(
            balance=10000,
            equity=10000,
            margin=0,
            free_margin=10000,
            margin_level=0,
            open_positions=0,
            total_trades=0
        )
        
        # Mock risk manager to allow trade
        self.mock_risk_manager.can_open_trade.return_value = (True, "All checks passed")
        
        # Mock trade executor to succeed
        mock_trade = Mock()
        mock_trade.trade_id = "TEST001"
        self.mock_trade_executor.execute_trade.return_value = mock_trade
        
        result = self.strategy.execute_signal(signal, account_info)
        
        self.assertTrue(result)
        self.mock_trade_executor.execute_trade.assert_called_once()
    
    def test_strategy_enable_disable(self):
        """Test strategy enable/disable functionality."""
        self.assertTrue(self.strategy.is_enabled())
        
        self.strategy.disable()
        self.assertFalse(self.strategy.is_enabled())
        
        self.strategy.enable()
        self.assertTrue(self.strategy.is_enabled())
    
    def test_get_strategy_summary(self):
        """Test strategy summary generation."""
        summary = self.strategy.get_strategy_summary()
    
    def test_statistical_randomness_validation(self):
        """Test statistical quality of random decision engine."""
        decision_engine = DecisionEngine()
        
        # Generate 1000 random decisions
        random_values = []
        entry_decisions = []
        
        for _ in range(1000):
            random_value = decision_engine.generate_random_value()
            random_values.append(random_value)
            
            # Test entry decision with default probability (0.6)
            should_enter, _ = decision_engine.should_enter_trade(confidence=1.0)
            entry_decisions.append(should_enter)
        
        # Test 1: Entry rate converges to configured probability
        entry_rate = sum(entry_decisions) / len(entry_decisions)
        expected_rate = RANDOM_DECISION['entry_probability']
        
        # Allow 5% margin of error
        self.assertAlmostEqual(entry_rate, expected_rate, delta=0.05,
                          msg=f"Entry rate {entry_rate:.4f} deviates from expected {expected_rate:.4f}")
        
        # Test 2: Range validation
        self.assertGreaterEqual(min(random_values), 0.0)
        self.assertLessEqual(max(random_values), 1.0)
    
    def test_news_filter_blackout_windows(self):
        """Test that news filter blocks trading during configured windows."""
        from src.core.market_analyzer import MarketAnalyzer
        import pytz
        
        analyzer = MarketAnalyzer()
        
        # Test during FOMC window (Wednesday 2 PM UTC)
        fomc_time = datetime(2024, 9, 18, 14, 30, tzinfo=pytz.UTC)  # Wednesday 2:30 PM UTC
        is_blocked = analyzer.is_news_time(fomc_time)
        self.assertTrue(is_blocked, "Should block during FOMC window")
        
        # Test during NFP window (Friday 8 AM UTC)
        nfp_time = datetime(2024, 9, 20, 8, 30, tzinfo=pytz.UTC)  # Friday 8:30 AM UTC
        is_blocked = analyzer.is_news_time(nfp_time)
        self.assertTrue(is_blocked, "Should block during NFP window")
        
        # Test outside news window (Monday 10 AM UTC)
        normal_time = datetime(2024, 9, 16, 10, 30, tzinfo=pytz.UTC)  # Monday 10:30 AM UTC
        is_blocked = analyzer.is_news_time(normal_time)
        self.assertFalse(is_blocked, "Should NOT block outside news windows")
        
        # Test during CPI window (Wednesday 8 AM UTC)
        cpi_time = datetime(2024, 9, 18, 8, 30, tzinfo=pytz.UTC)  # Wednesday 8:30 AM UTC
        is_blocked = analyzer.is_news_time(cpi_time)
        self.assertTrue(is_blocked, "Should block during CPI window")


if __name__ == '__main__':
    unittest.main()
