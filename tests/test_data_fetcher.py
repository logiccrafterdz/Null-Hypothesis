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
import pytz

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
        
        with patch("src.core.data_fetcher.DATA_SOURCE", "hybrid"):
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
        
        with patch("src.core.data_fetcher.DATA_SOURCE", "hybrid"):
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
        
        with patch("src.core.data_fetcher.DATA_SOURCE", "hybrid"):
            result = self.data_fetcher.get_data(
                symbol="XAUUSD",
                timeframe="M15",
                start_date=start_date,
                end_date=end_date
            )
        
        # Should return empty due to validation failure
        self.assertTrue(result.empty)

    def test_local_mode_raises_when_no_cache(self):
        """Local mode must fail loudly instead of silently returning empty data."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        with patch.object(self.data_fetcher, 'load_cached_data', return_value=None):
            with self.assertRaises(ValueError) as ctx:
                self.data_fetcher.get_data(
                    symbol="XAUUSD",
                    timeframe="M15",
                    start_date=start_date,
                    end_date=end_date
                )
        
        self.assertIn("XAUUSD", str(ctx.exception))
        self.assertIn("sample", str(ctx.exception))

    def test_local_mode_returns_cached_data(self):
        """Local mode returns cached fixtures covering the requested range."""
        idx = pd.date_range(end=datetime.now(), periods=200, freq='15min')
        cached = pd.DataFrame({
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000,
        }, index=idx)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        
        with patch.object(self.data_fetcher, 'load_cached_data', return_value=cached):
            result = self.data_fetcher.get_data(
                symbol="XAUUSD",
                timeframe="M15",
                start_date=start_date,
                end_date=end_date
            )
        
        self.assertFalse(result.empty)

    def test_naive_index_mixed_with_aware_dates(self):
        """Cached data with a naive index must still filter cleanly when the
        caller supplies tz-aware datetimes (and vice-versa), without
        tz-comparison crashes."""
        idx = pd.date_range(end=datetime.now(), periods=200, freq='15min')
        cached = pd.DataFrame({
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000,
        }, index=idx)

        aware_idx = idx.tz_localize('UTC')
        aware = cached.set_axis(aware_idx)

        end_date = datetime.now(pytz.UTC)
        start_date = end_date - timedelta(days=1)

        with patch.object(self.data_fetcher, 'load_cached_data', return_value=cached):
            result = self.data_fetcher.get_data(
                symbol="XAUUSD",
                timeframe="M15",
                start_date=start_date,
                end_date=end_date
            )
        self.assertFalse(result.empty)

        with patch.object(self.data_fetcher, 'load_cached_data', return_value=aware):
            result = self.data_fetcher.get_data(
                symbol="XAUUSD",
                timeframe="M15",
                start_date=datetime.now() - timedelta(days=1),
                end_date=datetime.now()
            )
        self.assertFalse(result.empty)
        self.assertTrue((result.index >= start_date).all())

    def test_generate_sample_data(self):
        """generate_sample_data produces valid seeded OHLCV data."""
        from src.utils.helpers import generate_sample_data

        df = generate_sample_data(asset="XAUUSD", days=7, timeframe="M15", seed=42)
        self.assertGreater(len(df), 100)
        self.assertIn('open', df.columns)
        self.assertIn('volume', df.columns)
        self.assertTrue((df['high'] >= df['low']).all())
        self.assertTrue(df.index.tz is not None)

        # Seeded generation is reproducible
        df2 = generate_sample_data(asset="XAUUSD", days=7, timeframe="M15", seed=42)
        pd.testing.assert_frame_equal(df, df2)

    def test_generate_sample_data_triggers_detector(self):
        """Capitulation candles in sample data must pass the production
        detector so a local demo backtest actually produces trades."""
        from src.utils.helpers import generate_sample_data
        from src.core.market_analyzer import MarketAnalyzer

        df = generate_sample_data(asset="XAUUSD", days=7, timeframe="M15", seed=42)
        analyzer = MarketAnalyzer()
        signals = 0
        for i in range(60, len(df)):
            sub = df.iloc[max(0, i - 40):i + 1]
            if analyzer.detect_bad_luck_moment(sub, "XAUUSD", sub.index[-1]):
                signals += 1

        self.assertGreater(signals, 0)


if __name__ == '__main__':
    unittest.main()
