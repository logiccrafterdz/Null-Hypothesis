"""
Market Analyzer for Phoenix Protocol Trading System
Implements Bad Luck Moment detection and market analysis.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pytz

from config.strategy_params import (
    BAD_LUCK_DETECTOR,
    NEWS_FILTER,
    TREND_FILTER,
    VOLATILITY_FILTER
)
from config.settings import NEWS_BLACKOUT_WINDOWS
from src.utils.logger import get_logger
from src.utils.indicators import (
    calculate_atr,
    calculate_volume_sma,
    is_reversal_pattern
)
from src.utils.helpers import is_trading_hours, ensure_utc

logger = get_logger()


class BadLuckMoment:
    """Represents a detected bad luck moment."""
    
    def __init__(
        self,
        asset: str,
        timestamp: datetime,
        conditions: Dict[str, any],
        accepted: bool,
        random_value: Optional[float] = None
    ):
        """
        Initialize bad luck moment.
        
        Args:
            asset: Asset symbol
            timestamp: Detection timestamp
            conditions: Detected conditions
            accepted: Whether trade was accepted
            random_value: Random decision value
        """
        self.asset = asset
        self.timestamp = timestamp
        self.conditions = conditions
        self.accepted = accepted
        self.random_value = random_value
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary."""
        return {
            'asset': self.asset,
            'timestamp': self.timestamp,
            'conditions': self.conditions,
            'accepted': self.accepted,
            'random_value': self.random_value
        }


class MarketAnalyzer:
    """Analyzes market conditions and detects bad luck moments."""
    
    def __init__(self):
        """Initialize market analyzer."""
        self.logger = get_logger()
        self.detected_moments: List[BadLuckMoment] = []
    
    def check_price_drop(
        self,
        df: pd.DataFrame,
        drop_threshold: float
    ) -> Tuple[bool, float]:
        """
        Check if price has dropped significantly.
        
        Args:
            df: DataFrame with OHLCV data
            drop_threshold: Drop threshold (0.03 = 3%)
            
        Returns:
            Tuple of (is_drop, drop_percentage)
        """
        if len(df) < 2:
            return False, 0.0
        
        current_close = df['close'].iloc[-1]
        previous_close = df['close'].iloc[-2]
        
        drop_pct = (previous_close - current_close) / previous_close
        is_drop = drop_pct >= drop_threshold
        
        return is_drop, drop_pct
    
    def check_volume_spike(
        self,
        df: pd.DataFrame,
        volume_multiplier: float,
        volume_period: int
    ) -> Tuple[bool, float]:
        """
        Check if volume has spiked.
        
        Args:
            df: DataFrame with OHLCV data
            volume_multiplier: Volume multiplier threshold
            volume_period: Period for volume average
            
        Returns:
            Tuple of (is_spike, spike_ratio)
        """
        if len(df) < volume_period + 1:
            return False, 0.0
        
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].iloc[-volume_period-1:-1].mean()
        
        if avg_volume == 0:
            return False, 0.0
        
        spike_ratio = current_volume / avg_volume
        is_spike = spike_ratio >= volume_multiplier
        
        return is_spike, spike_ratio
    
    def check_volatility_spike(
        self,
        df: pd.DataFrame,
        atr_multiplier: float,
        atr_period: int
    ) -> Tuple[bool, float]:
        """
        Check if volatility has spiked.
        
        Args:
            df: DataFrame with OHLCV data
            atr_multiplier: ATR multiplier threshold
            atr_period: ATR period
            
        Returns:
            Tuple of (is_spike, spike_ratio)
        """
        if len(df) < atr_period + 1:
            return False, 0.0
        
        atr = calculate_atr(df, atr_period)
        current_atr = atr.iloc[-1]
        avg_atr = atr.iloc[-atr_period-1:-1].mean()
        
        if avg_atr == 0 or np.isnan(avg_atr):
            return False, 0.0
        
        spike_ratio = current_atr / avg_atr
        is_spike = spike_ratio >= atr_multiplier
        
        return is_spike, spike_ratio
    
    def check_reversal_pattern(
        self,
        df: pd.DataFrame,
        patterns: List[str]
    ) -> Tuple[bool, str]:
        """
        Check if reversal pattern is present.
        
        Args:
            df: DataFrame with OHLCV data
            patterns: List of pattern names to check
            
        Returns:
            Tuple of (is_reversal, pattern_name)
        """
        if len(df) < 3:
            return False, "None"
        
        reversal_detected = is_reversal_pattern(df, patterns)
        
        if reversal_detected.iloc[-1]:
            # Determine which pattern was detected
            for pattern in patterns:
                pattern_signal = is_reversal_pattern(df, [pattern])
                if pattern_signal.iloc[-1]:
                    return True, pattern
        
        return False, "None"
    
    def is_news_time(self, current_time: datetime) -> bool:
        """
        Check if current time is near a major news event.
        
        Args:
            current_time: Current datetime
            
        Returns:
            True if near news event
        """
        if not NEWS_FILTER['enabled']:
            return False
        
        # Check against configured news blackout windows
        for window in NEWS_BLACKOUT_WINDOWS:
            try:
                # Get timezone for this window
                tz = pytz.timezone(window['timezone'])
                localized_time = ensure_utc(current_time).astimezone(tz)
                
                # Check if day matches
                if localized_time.weekday() == window['day_of_week']:
                    # Check if time is within window
                    if window['start_hour'] <= localized_time.hour < window['end_hour']:
                        self.logger.debug(f"News blackout window active: {window['reason']}")
                        return True
            except Exception as e:
                self.logger.warning(f"Error checking news window {window}: {e}")
                continue
        
        return False
    
    def precompute_verdict_mask(
        self,
        df: pd.DataFrame,
        asset: str
    ) -> pd.Series:
        """
        Vectorized pre-filter for detect_bad_luck_moment.

        Returns a boolean Series aligned to ``df.index`` that is True exactly
        where the per-bar detector (with a bounded window) would return a
        BadLuckMoment. All component indicators use fixed rolling windows, so
        the value at a position does not depend on how much history precedes
        the window; this mask is therefore identical to the windowed checks.
        Used by the backtester to avoid running the expensive per-bar detector
        on every candle (the detector is still the authoritative oracle).

        Args:
            df: DataFrame with OHLCV data
            asset: Asset symbol

        Returns:
            Boolean Series (True = candidate bad luck moment)
        """
        # Time gates first (only depend on the timestamp, not the window).
        in_hours = pd.Series(
            [is_trading_hours(ts, asset) for ts in df.index], index=df.index
        )
        near_news = pd.Series(
            [self.is_news_time(ts) for ts in df.index], index=df.index
        )

        # Price drop: (prev_close - close) / prev_close >= drop_threshold.
        prev_close = df['close'].shift(1)
        drop_pct = (prev_close - df['close']) / prev_close
        drop_met = drop_pct >= BAD_LUCK_DETECTOR['drop_threshold']

        # Volume spike: volume vs mean of the *previous* volume_period bars.
        volume_period = BAD_LUCK_DETECTOR['volume_period']
        vol_avg = df['volume'].shift(1).rolling(volume_period).mean()
        vol_ratio = df['volume'] / vol_avg
        volume_met = (
            (vol_ratio >= BAD_LUCK_DETECTOR['volume_multiplier']) &
            (vol_avg > 0)
        )

        # Volatility spike: ATR vs mean of the *previous* atr_period ATRs.
        atr_period = BAD_LUCK_DETECTOR['atr_period']
        atr = calculate_atr(df, atr_period)
        atr_avg = atr.shift(1).rolling(atr_period).mean()
        atr_ratio = atr / atr_avg
        volatility_met = (
            (atr_ratio >= BAD_LUCK_DETECTOR['atr_multiplier']) &
            (atr_avg > 0)
        )

        # Reversal pattern (position-invariant candlestick logic).
        reversal_met = is_reversal_pattern(
            df, BAD_LUCK_DETECTOR['reversal_patterns']
        ).astype(bool)

        return (
            in_hours & ~near_news & drop_met & volume_met &
            volatility_met & reversal_met
        )

    def detect_bad_luck_moment(
        self,
        df: pd.DataFrame,
        asset: str,
        current_time: Optional[datetime] = None
    ) -> Optional[BadLuckMoment]:
        """
        Detect if current market conditions represent a bad luck moment.
        
        Args:
            df: DataFrame with OHLCV data
            asset: Asset symbol
            current_time: Current datetime (defaults to now)
            
        Returns:
            BadLuckMoment object or None
        """
        if current_time is None:
            current_time = datetime.now(pytz.UTC)
        else:
            # Interpret naive datetimes as UTC so trading/news windows
            # are always evaluated consistently.
            current_time = ensure_utc(current_time)
        
        # Check if within trading hours
        if not is_trading_hours(current_time, asset):
            return None
        
        # Check if near news time
        if self.is_news_time(current_time):
            self.logger.debug(f"Near news time for {asset}, skipping")
            return None
        
        # Check all conditions
        conditions = {}
        
        # Price drop
        is_drop, drop_pct = self.check_price_drop(
            df,
            BAD_LUCK_DETECTOR['drop_threshold']
        )
        conditions['price_drop'] = drop_pct
        conditions['price_drop_met'] = is_drop
        
        # Volume spike
        is_volume_spike, volume_ratio = self.check_volume_spike(
            df,
            BAD_LUCK_DETECTOR['volume_multiplier'],
            BAD_LUCK_DETECTOR['volume_period']
        )
        conditions['volume_spike'] = volume_ratio
        conditions['volume_spike_met'] = is_volume_spike
        
        # Volatility spike
        is_volatility_spike, volatility_ratio = self.check_volatility_spike(
            df,
            BAD_LUCK_DETECTOR['atr_multiplier'],
            BAD_LUCK_DETECTOR['atr_period']
        )
        conditions['volatility_spike'] = volatility_ratio
        conditions['volatility_spike_met'] = is_volatility_spike
        
        # Reversal pattern
        is_reversal, pattern_name = self.check_reversal_pattern(
            df,
            BAD_LUCK_DETECTOR['reversal_patterns']
        )
        conditions['reversal_pattern'] = pattern_name
        conditions['reversal_pattern_met'] = is_reversal
        
        # Check if all conditions are met
        all_conditions_met = (
            is_drop and
            is_volume_spike and
            is_volatility_spike and
            is_reversal
        )
        
        if not all_conditions_met:
            self.logger.debug(f"Bad luck moment not detected for {asset}: {conditions}")
            return None
        
        self.logger.info(f"Bad luck moment detected for {asset}: {conditions}")
        
        # Create bad luck moment (will be decided by decision engine)
        moment = BadLuckMoment(
            asset=asset,
            timestamp=current_time,
            conditions=conditions,
            accepted=False  # Will be set by decision engine
        )
        
        self.detected_moments.append(moment)
        return moment
    
    def apply_trend_filter(self, df: pd.DataFrame) -> bool:
        """
        Apply trend filter if enabled.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            True if trend filter passes
        """
        if not TREND_FILTER['enabled']:
            return True
        
        # Implement trend filter logic here
        # For now, just return True
        return True
    
    def apply_volatility_filter(self, df: pd.DataFrame) -> bool:
        """
        Apply volatility filter if enabled.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            True if volatility filter passes
        """
        if not VOLATILITY_FILTER['enabled']:
            return True
        
        atr = calculate_atr(df, BAD_LUCK_DETECTOR['atr_period'])
        current_atr = atr.iloc[-1]
        
        if current_atr < VOLATILITY_FILTER['min_atr']:
            self.logger.debug(f"ATR too low: {current_atr}")
            return False
        
        if current_atr > VOLATILITY_FILTER['max_atr']:
            self.logger.debug(f"ATR too high: {current_atr}")
            return False
        
        return True
    
    def analyze_market_state(
        self,
        df: pd.DataFrame,
        asset: str
    ) -> Dict[str, any]:
        """
        Analyze current market state.
        
        Args:
            df: DataFrame with OHLCV data
            asset: Asset symbol
            
        Returns:
            Dictionary with market state information
        """
        state = {
            'asset': asset,
            'timestamp': datetime.now(pytz.UTC),
            'current_price': df['close'].iloc[-1],
            'price_change_pct': (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2],
        }
        
        # Calculate indicators
        atr = calculate_atr(df, BAD_LUCK_DETECTOR['atr_period'])
        state['atr'] = atr.iloc[-1]
        
        volume_sma = calculate_volume_sma(df, BAD_LUCK_DETECTOR['volume_period'])
        state['volume_ratio'] = df['volume'].iloc[-1] / volume_sma.iloc[-1]
        
        # Check trend
        state['trend'] = 'neutral'
        if df['close'].iloc[-1] > df['close'].iloc[-5]:
            state['trend'] = 'bullish'
        elif df['close'].iloc[-1] < df['close'].iloc[-5]:
            state['trend'] = 'bearish'
        
        return state
    
    def get_detected_moments(
        self,
        asset: Optional[str] = None,
        limit: int = 100
    ) -> List[BadLuckMoment]:
        """
        Get detected bad luck moments.
        
        Args:
            asset: Filter by asset (None for all)
            limit: Maximum number to return
            
        Returns:
            List of BadLuckMoment objects
        """
        moments = self.detected_moments
        
        if asset:
            moments = [m for m in moments if m.asset == asset]
        
        return moments[-limit:]
    
    def clear_detected_moments(self) -> None:
        """Clear all detected moments."""
        self.detected_moments.clear()
        self.logger.info("Cleared all detected bad luck moments")
