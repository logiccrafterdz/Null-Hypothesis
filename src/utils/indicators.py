"""
Technical Indicators for Null Hypothesis Trading System
Custom technical indicators for market analysis.
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR).
    
    Args:
        df: DataFrame with OHLC data
        period: ATR period
        
    Returns:
        ATR series
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return atr


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).
    
    Args:
        df: DataFrame with close prices
        period: RSI period
        
    Returns:
        RSI series
    """
    close = df['close']
    delta = close.diff()
    
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_ema(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA).
    
    Args:
        df: DataFrame with close prices
        period: EMA period
        
    Returns:
        EMA series
    """
    return df['close'].ewm(span=period, adjust=False).mean()


def calculate_sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Calculate Simple Moving Average (SMA).
    
    Args:
        df: DataFrame with close prices
        period: SMA period
        
    Returns:
        SMA series
    """
    return df['close'].rolling(window=period).mean()


def calculate_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands.
    
    Args:
        df: DataFrame with close prices
        period: Period for moving average
        std_dev: Standard deviation multiplier
        
    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    middle_band = calculate_sma(df, period)
    std = df['close'].rolling(window=period).std()
    
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    
    return upper_band, middle_band, lower_band


def calculate_macd(
    df: pd.DataFrame,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    Args:
        df: DataFrame with close prices
        fast_period: Fast EMA period
        slow_period: Slow EMA period
        signal_period: Signal line period
        
    Returns:
        Tuple of (macd_line, signal_line, histogram)
    """
    fast_ema = calculate_ema(df, fast_period)
    slow_ema = calculate_ema(df, slow_period)
    
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def calculate_volume_sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Calculate Volume Simple Moving Average.
    
    Args:
        df: DataFrame with volume data
        period: SMA period
        
    Returns:
        Volume SMA series
    """
    return df['volume'].rolling(window=period).mean()


def detect_hammer(df: pd.DataFrame) -> pd.Series:
    """
    Detect hammer candlestick pattern.
    
    Args:
        df: DataFrame with OHLC data
        
    Returns:
        Boolean series indicating hammer pattern
    """
    body = df['close'] - df['open']
    body_abs = body.abs()
    range_ = df['high'] - df['low']
    upper_shadow = df['high'] - df[['open', 'close']].max(axis=1)
    lower_shadow = df[['open', 'close']].min(axis=1) - df['low']
    
    # Hammer criteria
    is_hammer = (
        (lower_shadow >= 2 * body_abs) &  # Long lower shadow
        (upper_shadow <= body_abs) &      # Short upper shadow
        (body_abs <= range_ * 0.3)        # Small body
    )
    
    return is_hammer


def detect_doji(df: pd.DataFrame) -> pd.Series:
    """
    Detect doji candlestick pattern.
    
    Args:
        df: DataFrame with OHLC data
        
    Returns:
        Boolean series indicating doji pattern
    """
    body = (df['close'] - df['open']).abs()
    range_ = df['high'] - df['low']
    
    # Doji criteria (very small body)
    is_doji = body <= range_ * 0.1
    
    return is_doji


def detect_engulfing_bullish(df: pd.DataFrame) -> pd.Series:
    """
    Detect bullish engulfing pattern.
    
    Args:
        df: DataFrame with OHLC data
        
    Returns:
        Boolean series indicating bullish engulfing
    """
    current_body = df['close'] - df['open']
    previous_body = df['close'].shift() - df['open'].shift()
    
    current_green = current_body > 0
    previous_red = previous_body < 0
    
    # Engulfing criteria
    is_engulfing = (
        current_green &
        previous_red &
        (df['close'] > df['open'].shift()) &  # Current close above previous open
        (df['open'] < df['close'].shift())    # Current open below previous close
    )
    
    return is_engulfing


def detect_morning_star(df: pd.DataFrame) -> pd.Series:
    """
    Detect morning star pattern (3-candle bullish reversal).
    
    Args:
        df: DataFrame with OHLC data
        
    Returns:
        Boolean series indicating morning star
    """
    # Need 3 candles
    if len(df) < 3:
        return pd.Series([False] * len(df), index=df.index)
    
    body1 = df['close'].shift(2) - df['open'].shift(2)
    body2 = df['close'].shift(1) - df['open'].shift(1)
    body3 = df['close'] - df['open']
    
    # Morning star criteria
    is_morning_star = (
        (body1 < 0) &  # First candle bearish
        (body2.abs() < body1.abs()) &  # Second candle small body
        (body3 > 0) &  # Third candle bullish
        (df['close'] > (df['open'].shift(2) + df['close'].shift(2)) / 2)  # Close above midpoint of first candle
    )
    
    return is_morning_star


def detect_piercing(df: pd.DataFrame) -> pd.Series:
    """
    Detect piercing pattern (bullish reversal).
    
    Args:
        df: DataFrame with OHLC data
        
    Returns:
        Boolean series indicating piercing pattern
    """
    previous_body = df['close'].shift() - df['open'].shift()
    current_body = df['close'] - df['open']
    
    # Piercing criteria
    is_piercing = (
        (previous_body < 0) &  # Previous candle bearish
        (current_body > 0) &  # Current candle bullish
        (df['open'] < df['close'].shift()) &  # Gap down open
        (df['close'] > (df['open'].shift() + df['close'].shift()) / 2)  # Close above midpoint
    )
    
    return is_piercing


def is_reversal_pattern(df: pd.DataFrame, patterns: list) -> pd.Series:
    """
    Check if any reversal pattern is present.
    
    Args:
        df: DataFrame with OHLC data
        patterns: List of pattern names to check
        
    Returns:
        Boolean series indicating any reversal pattern
    """
    pattern_functions = {
        'hammer': detect_hammer,
        'doji': detect_doji,
        'engulfing_bullish': detect_engulfing_bullish,
        'morning_star': detect_morning_star,
        'piercing': detect_piercing,
    }
    
    reversal_detected = pd.Series([False] * len(df), index=df.index)
    
    for pattern in patterns:
        if pattern in pattern_functions:
            pattern_signal = pattern_functions[pattern](df)
            reversal_detected = reversal_detected | pattern_signal
    
    return reversal_detected


def calculate_support_resistance(
    df: pd.DataFrame,
    window: int = 20,
    num_levels: int = 3
) -> Tuple[list, list]:
    """
    Calculate support and resistance levels.
    
    Args:
        df: DataFrame with OHLC data
        window: Lookback window
        num_levels: Number of levels to return
        
    Returns:
        Tuple of (support_levels, resistance_levels)
    """
    recent_df = df.tail(window)
    
    # Find local minima and maxima
    lows = recent_df['low'].values
    highs = recent_df['high'].values
    
    # Simple approach: use percentile-based levels
    support_levels = np.percentile(lows, [10, 25, 50])[:num_levels]
    resistance_levels = np.percentile(highs, [90, 75, 50])[:num_levels]
    
    return support_levels.tolist(), resistance_levels.tolist()


def calculate_trend_strength(df: pd.DataFrame, period: int = 20) -> float:
    """
    Calculate trend strength using linear regression slope.
    
    Args:
        df: DataFrame with close prices
        period: Period for calculation
        
    Returns:
        Trend strength value
    """
    close_prices = df['close'].tail(period).values
    
    if len(close_prices) < 2:
        return 0.0
    
    x = np.arange(len(close_prices))
    slope, _ = np.polyfit(x, close_prices, 1)
    
    # Normalize by average price
    avg_price = np.mean(close_prices)
    normalized_slope = slope / avg_price
    
    return normalized_slope
