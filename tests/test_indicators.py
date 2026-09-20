"""
Unit tests for technical indicators.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.indicators import (
    calculate_atr,
    calculate_rsi,
    calculate_ema,
    calculate_sma,
    calculate_bollinger_bands,
    calculate_macd,
    detect_hammer,
    detect_doji,
    detect_engulfing_bullish
)


class TestIndicators(unittest.TestCase):
    """Test technical indicators."""
    
    def setUp(self):
        """Set up test data."""
        # Generate sample OHLCV data
        np.random.seed(42)
        dates = pd.date_range(start=datetime.now() - timedelta(days=100), periods=100, freq='D')
        
        close_prices = 100 + np.cumsum(np.random.normal(0, 1, 100))
        high_prices = close_prices + np.random.uniform(0, 2, 100)
        low_prices = close_prices - np.random.uniform(0, 2, 100)
        open_prices = close_prices + np.random.uniform(-1, 1, 100)
        volumes = np.random.uniform(1000, 5000, 100)
        
        self.df = pd.DataFrame({
            'open': open_prices,
            'high': high_prices,
            'low': low_prices,
            'close': close_prices,
            'volume': volumes
        }, index=dates)
    
    def test_calculate_atr(self):
        """Test ATR calculation."""
        atr = calculate_atr(self.df, period=14)
        
        # Check that ATR is calculated
        self.assertIsNotNone(atr)
        self.assertEqual(len(atr), len(self.df))
        
        # Check that ATR values are positive (excluding NaN values)
        valid_atr = atr.dropna()
        self.assertTrue((valid_atr > 0).all())
        
        # Check that first values are NaN (due to rolling window)
        self.assertTrue(pd.isna(atr.iloc[0]))
    
    def test_calculate_rsi(self):
        """Test RSI calculation."""
        rsi = calculate_rsi(self.df, period=14)
        
        # Check that RSI is calculated
        self.assertIsNotNone(rsi)
        self.assertEqual(len(rsi), len(self.df))
        
        # Check that RSI values are between 0 and 100
        valid_rsi = rsi.dropna()
        self.assertTrue((valid_rsi >= 0).all())
        self.assertTrue((valid_rsi <= 100).all())
    
    def test_calculate_ema(self):
        """Test EMA calculation."""
        ema = calculate_ema(self.df, period=20)
        
        # Check that EMA is calculated
        self.assertIsNotNone(ema)
        self.assertEqual(len(ema), len(self.df))
        
        # Check that EMA values are reasonable
        self.assertTrue((ema > 0).all())
    
    def test_calculate_sma(self):
        """Test SMA calculation."""
        sma = calculate_sma(self.df, period=20)
        
        # Check that SMA is calculated
        self.assertIsNotNone(sma)
        self.assertEqual(len(sma), len(self.df))
        
        # Check that SMA values are reasonable
        valid_sma = sma.dropna()
        self.assertTrue((valid_sma > 0).all())
    
    def test_calculate_bollinger_bands(self):
        """Test Bollinger Bands calculation."""
        upper, middle, lower = calculate_bollinger_bands(self.df, period=20, std_dev=2.0)
        
        # Check that all bands are calculated
        self.assertIsNotNone(upper)
        self.assertIsNotNone(middle)
        self.assertIsNotNone(lower)
        
        # Check that upper > middle > lower
        valid_mask = ~(pd.isna(upper) | pd.isna(middle) | pd.isna(lower))
        self.assertTrue((upper[valid_mask] >= middle[valid_mask]).all())
        self.assertTrue((middle[valid_mask] >= lower[valid_mask]).all())
    
    def test_calculate_macd(self):
        """Test MACD calculation."""
        macd_line, signal_line, histogram = calculate_macd(self.df)
        
        # Check that all components are calculated
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        self.assertIsNotNone(histogram)
        
        # Check that histogram = macd - signal
        valid_mask = ~(pd.isna(macd_line) | pd.isna(signal_line) | pd.isna(histogram))
        diff = macd_line[valid_mask] - signal_line[valid_mask]
        np.testing.assert_array_almost_equal(diff.values, histogram[valid_mask].values, decimal=10)
    
    def test_detect_hammer(self):
        """Test hammer pattern detection."""
        # Create a hammer pattern manually
        hammer_df = self.df.copy()
        hammer_df.iloc[-1] = {
            'open': 100,
            'high': 101,
            'low': 95,
            'close': 100.5,
            'volume': 2000
        }
        
        hammer_signal = detect_hammer(hammer_df)
        
        # Check that signal is a boolean series
        self.assertIsInstance(hammer_signal, pd.Series)
        self.assertEqual(len(hammer_signal), len(hammer_df))
    
    def test_detect_doji(self):
        """Test doji pattern detection."""
        # Create a doji pattern manually
        doji_df = self.df.copy()
        doji_df.iloc[-1] = {
            'open': 100,
            'high': 101,
            'low': 99,
            'close': 100,
            'volume': 2000
        }
        
        doji_signal = detect_doji(doji_df)
        
        # Check that signal is a boolean series
        self.assertIsInstance(doji_signal, pd.Series)
        self.assertEqual(len(doji_signal), len(doji_df))
    
    def test_detect_engulfing_bullish(self):
        """Test bullish engulfing pattern detection."""
        # Create bullish engulfing pattern manually
        engulfing_df = self.df.copy()
        engulfing_df.iloc[-2] = {
            'open': 100,
            'high': 101,
            'low': 99,
            'close': 99.5,
            'volume': 2000
        }
        engulfing_df.iloc[-1] = {
            'open': 99.3,
            'high': 102,
            'low': 99,
            'close': 101.5,
            'volume': 3000
        }
        
        engulfing_signal = detect_engulfing_bullish(engulfing_df)
        
        # Check that signal is a boolean series
        self.assertIsInstance(engulfing_signal, pd.Series)
        self.assertEqual(len(engulfing_signal), len(engulfing_df))


if __name__ == '__main__':
    unittest.main()
