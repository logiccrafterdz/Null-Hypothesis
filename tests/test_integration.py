"""
Integration tests for Null Hypothesis end-to-end workflow.
Tests the complete trading pipeline from data fetch to trade execution.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
import pandas as pd
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.data_fetcher import DataFetcher
from src.core.market_analyzer import MarketAnalyzer, BadLuckMoment
from src.core.decision_engine import DecisionEngine
from src.core.trade_executor import TradeExecutor
from src.core.risk_manager import RiskManager
from src.api.broker_interface import UnifiedBroker, AccountInfo, Order
from config.strategy_params import BAD_LUCK_DETECTOR, RANDOM_DECISION


class TestIntegration(unittest.TestCase):
    """Test end-to-end trading pipeline integration."""
    
    def setUp(self):
        """Set up test fixtures with mocked components."""
        # Create mock broker (use plain Mock to allow dynamic attributes)
        self.mock_broker = Mock()
        
        # Initialize real components with mocked dependencies
        self.data_fetcher = DataFetcher(self.mock_broker)
        self.market_analyzer = MarketAnalyzer()
        self.decision_engine = DecisionEngine()
        self.risk_manager = RiskManager()
        self.trade_executor = TradeExecutor(self.mock_broker, self.risk_manager)
        
        # Account info mock
        self.account_info = AccountInfo(
            balance=10000.0,
            equity=10000.0,
            margin=0.0,
            free_margin=10000.0,
            margin_level=0.0,
            open_positions=0,
            total_trades=0
        )
    
    def test_pipeline_with_no_bad_luck_moment(self):
        """Test pipeline when no bad luck moment is detected."""
        # Normal data without bad luck moment
        normal_data = pd.DataFrame({
            'open': [100.0, 101.0, 102.0, 103.0, 104.0],
            'high': [101.0, 102.0, 103.0, 104.0, 105.0],
            'low': [99.0, 100.0, 101.0, 102.0, 103.0],
            'close': [100.5, 101.5, 102.5, 103.5, 104.5],
            'volume': [1000, 1100, 1200, 1300, 1400]
        })
        
        self.mock_broker.get_broker_for_asset.return_value = self.mock_broker
        self.mock_broker.get_historical_data.return_value = normal_data
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        with patch("src.core.data_fetcher.DATA_SOURCE", "hybrid"), \
                patch.object(self.data_fetcher, 'save_cached_data', return_value=True):
            data = self.data_fetcher.get_data(
                symbol="XAUUSD",
                timeframe="M15",
                start_date=start_date,
                end_date=end_date
            )
        
        # Should not detect bad luck moment
        bad_luck_moment = self.market_analyzer.detect_bad_luck_moment(
            df=data,
            asset="XAUUSD",
            current_time=datetime.now()
        )
        
        self.assertIsNone(bad_luck_moment)
    
    def test_pipeline_with_risk_blocking(self):
        """Test pipeline when risk manager blocks trade."""
        # Set up risk manager to block trades
        self.risk_manager.daily_pnl = -600.0  # 6% loss (above 5% limit)
        
        # Check if trade can be opened
        can_open, reason = self.risk_manager.can_open_trade(
            account_info=self.account_info,
            open_positions=[],
            asset="XAUUSD"
        )
        
        # Should be blocked by daily loss limit
        self.assertFalse(can_open)


if __name__ == '__main__':
    unittest.main()
