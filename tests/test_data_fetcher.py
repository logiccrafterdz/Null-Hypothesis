"""
Unit tests for data fetcher component.
Tests data fetching, caching, error handling, and data validation.
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
from src.api.broker_interface import UnifiedBroker


class TestDataFetcher(unittest.TestCase):
    """Test data fetcher functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_broker = Mock()  # Use plain Mock to allow dynamic attributes
        self.data_fetcher = DataFetcher(self.mock_broker)
        
        # Sample OHLCV data
        self.sample_data = pd.DataFrame({
            'open': [100.0, 101.0, 102.0, 103.0, 104.0],
            'high': [101.0, 102.0, 103.0, 104.0, 105.0],
            'low': [99.0, 100.0, 101.0, 102.0, 103.0],
            'close': [100.5, 101.5, 102.5, 103.5, 104.5],
            'volume': [1000, 1100, 1200, 1300, 1400]
        })
    
    def test_initialization(self):
        """Test data fetcher initialization."""
        self.assertIsNotNone(self.data_fetcher)
        self.assertEqual(self.data_fetcher.unified_broker, self.mock_broker)
    
    def test_get_data_no_broker(self):
        """Test handling when no broker is configured."""
        self.mock_broker.get_broker_for_asset.return_value = None
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        result = self.data_fetcher.get_data(
            symbol="XAUUSD",
            timeframe="M15",
            start_date=start_date,
            end_date=end_date
        )
        
        self.assertTrue(result.empty)
    
    def test_get_data_connection_failure(self):
        """Test handling of connection failure."""
        # Mock broker to raise exception
        self.mock_broker.get_broker_for_asset.return_value = self.mock_broker
        self.mock_broker.get_historical_data.side_effect = ConnectionError("Connection failed")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        result = self.data_fetcher.get_data(
            symbol="XAUUSD",
            timeframe="M15",
            start_date=start_date,
            end_date=end_date
        )
        
        self.assertTrue(result.empty)
    
    def test_data_validation(self):
        """Test data validation for required columns."""
        # Invalid data missing 'volume' column
        invalid_data = pd.DataFrame({
            'open': [100.0, 101.0],
            'high': [101.0, 102.0],
            'low': [99.0, 100.0],
            'close': [100.5, 101.5]
        })
        
        self.mock_broker.get_broker_for_asset.return_value = self.mock_broker
        self.mock_broker.get_historical_data.return_value = invalid_data
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        result = self.data_fetcher.get_data(
            symbol="XAUUSD",
            timeframe="M15",
            start_date=start_date,
            end_date=end_date
        )
        
        # Should return empty due to validation failure
        self.assertTrue(result.empty)


if __name__ == '__main__':
    unittest.main()
