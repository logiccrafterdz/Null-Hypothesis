"""
Volatility Filter for Phoenix Protocol Trading System
Optional volatility-based filter for additional signal confirmation.
"""

import pandas as pd
from typing import Dict, Tuple

from config.strategy_params import VOLATILITY_FILTER
from src.utils.logger import get_logger
from src.utils.indicators import calculate_atr


class VolatilityFilter:
    """
    Volatility filter for trading signals.
    Filters signals based on market volatility levels.
    """
    
    def __init__(self):
        """Initialize volatility filter."""
        self.logger = get_logger()
        self.enabled = VOLATILITY_FILTER['enabled']
        self.min_atr = VOLATILITY_FILTER['min_atr']
        self.max_atr = VOLATILITY_FILTER['max_atr']
        self.atr_period = 14
    
    def check_signal(
        self,
        df: pd.DataFrame
    ) -> Tuple[bool, str]:
        """
        Check if signal passes volatility filter.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Tuple of (passes_filter, reason)
        """
        if not self.enabled:
            return True, "Volatility filter disabled"
        
        if len(df) < self.atr_period:
            return True, "Insufficient data for volatility check"
        
        atr = calculate_atr(df, self.atr_period)
        current_atr = atr.iloc[-1]
        
        if current_atr < self.min_atr:
            return False, f"ATR too low: {current_atr:.6f} < {self.min_atr}"
        
        if current_atr > self.max_atr:
            return False, f"ATR too high: {current_atr:.6f} > {self.max_atr}"
        
        return True, f"Volatility within range: {current_atr:.6f}"
    
    def get_volatility_info(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Get detailed volatility information.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Dictionary with volatility information
        """
        if len(df) < self.atr_period:
            return {
                'atr': 0.0,
                'atr_pct': 0.0,
                'enabled': self.enabled,
                'within_range': False
            }
        
        atr = calculate_atr(df, self.atr_period)
        current_atr = atr.iloc[-1]
        current_price = df['close'].iloc[-1]
        atr_pct = current_atr / current_price
        
        within_range = self.min_atr <= current_atr <= self.max_atr
        
        return {
            'atr': current_atr,
            'atr_pct': atr_pct,
            'min_atr': self.min_atr,
            'max_atr': self.max_atr,
            'within_range': within_range,
            'enabled': self.enabled,
            'period': self.atr_period
        }
    
    def is_volatility_normal(self, df: pd.DataFrame) -> bool:
        """
        Check if volatility is within normal range.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            True if volatility is normal
        """
        passes, _ = self.check_signal(df)
        return passes
