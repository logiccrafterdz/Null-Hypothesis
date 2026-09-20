"""
Trend Filter for Phoenix Protocol Trading System
Optional trend-based filter for additional signal confirmation.
"""

import pandas as pd
from typing import Dict, Optional, Tuple

from config.strategy_params import TREND_FILTER
from src.utils.logger import get_logger
from src.utils.indicators import calculate_ema, calculate_sma, calculate_trend_strength


class TrendFilter:
    """
    Trend filter for trading signals.
    Can be used to only trade in the direction of the trend.
    """
    
    def __init__(self):
        """Initialize trend filter."""
        self.logger = get_logger()
        self.enabled = TREND_FILTER['enabled']
        self.trend_indicator = TREND_FILTER['trend_indicator']
        self.trend_period = TREND_FILTER['trend_period']
        self.trade_with_trend = TREND_FILTER['trade_with_trend']
    
    def calculate_trend(self, df: pd.DataFrame) -> str:
        """
        Calculate current trend direction.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Trend direction ('bullish', 'bearish', 'neutral')
        """
        if len(df) < self.trend_period:
            return 'neutral'
        
        if self.trend_indicator == 'EMA':
            ma = calculate_ema(df, self.trend_period)
        elif self.trend_indicator == 'SMA':
            ma = calculate_sma(df, self.trend_period)
        else:
            ma = calculate_sma(df, self.trend_period)
        
        current_price = df['close'].iloc[-1]
        current_ma = ma.iloc[-1]
        
        # Calculate trend strength
        trend_strength = calculate_trend_strength(df, self.trend_period)
        
        if current_price > current_ma and trend_strength > 0:
            return 'bullish'
        elif current_price < current_ma and trend_strength < 0:
            return 'bearish'
        else:
            return 'neutral'
    
    def check_signal(
        self,
        df: pd.DataFrame,
        signal_direction: str
    ) -> Tuple[bool, str]:
        """
        Check if signal passes trend filter.
        
        Args:
            df: DataFrame with OHLCV data
            signal_direction: Signal direction ('LONG' or 'SHORT')
            
        Returns:
            Tuple of (passes_filter, reason)
        """
        if not self.enabled:
            return True, "Trend filter disabled"
        
        trend = self.calculate_trend(df)
        
        if trend == 'neutral':
            return True, "Trend neutral, allowing signal"
        
        if self.trade_with_trend:
            # Only trade with trend
            if signal_direction == 'LONG' and trend == 'bullish':
                return True, f"Signal aligns with {trend} trend"
            elif signal_direction == 'SHORT' and trend == 'bearish':
                return True, f"Signal aligns with {trend} trend"
            else:
                return False, f"Signal against {trend} trend"
        else:
            # Trade against trend (fade the trend)
            if signal_direction == 'LONG' and trend == 'bearish':
                return True, f"Signal fading {trend} trend"
            elif signal_direction == 'SHORT' and trend == 'bullish':
                return True, f"Signal fading {trend} trend"
            else:
                return False, f"Signal not fading {trend} trend"
    
    def get_trend_info(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Get detailed trend information.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Dictionary with trend information
        """
        if len(df) < self.trend_period:
            return {
                'trend': 'neutral',
                'trend_strength': 0.0,
                'enabled': self.enabled
            }
        
        trend = self.calculate_trend(df)
        trend_strength = calculate_trend_strength(df, self.trend_period)
        
        if self.trend_indicator == 'EMA':
            ma = calculate_ema(df, self.trend_period)
        else:
            ma = calculate_sma(df, self.trend_period)
        
        current_price = df['close'].iloc[-1]
        current_ma = ma.iloc[-1]
        distance_from_ma = (current_price - current_ma) / current_ma
        
        return {
            'trend': trend,
            'trend_strength': trend_strength,
            'current_price': current_price,
            'moving_average': current_ma,
            'distance_from_ma_pct': distance_from_ma,
            'enabled': self.enabled,
            'indicator': self.trend_indicator,
            'period': self.trend_period
        }
