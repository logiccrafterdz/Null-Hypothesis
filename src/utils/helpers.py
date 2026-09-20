"""
Helper Functions for Phoenix Protocol Trading System
Common utility functions used across the system.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pytz


def format_currency(value: float, currency: str = "USD") -> str:
    """
    Format value as currency string.
    
    Args:
        value: Numeric value
        currency: Currency symbol
        
    Returns:
        Formatted currency string
    """
    return f"{currency} {value:,.2f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    Format value as percentage string.
    
    Args:
        value: Numeric value (0.01 = 1%)
        decimals: Number of decimal places
        
    Returns:
        Formatted percentage string
    """
    return f"{value * 100:.{decimals}f}%"


def calculate_position_size(
    capital: float,
    risk_percentage: float,
    stop_loss_pct: float,
    entry_price: float,
    asset: str = "EURUSD"
) -> float:
    """
    Calculate position size based on risk percentage with pip value integration.
    
    Args:
        capital: Available capital
        risk_percentage: Risk per trade (0.02 = 2%)
        stop_loss_pct: Stop loss percentage (0.015 = 1.5%)
        entry_price: Entry price
        asset: Asset symbol for pip calculation
        
    Returns:
        Position size in units
    """
    risk_amount = capital * risk_percentage
    stop_loss_amount = entry_price * stop_loss_pct
    
    # Get pip location for asset
    pip_location = get_pip_location(asset)
    
    # Calculate position size with pip value consideration
    position_size = risk_amount / stop_loss_amount
    
    # Adjust for pip value if applicable
    if pip_location:
        pip_size = 10 ** (-pip_location)
        position_size = position_size / pip_size
    
    return position_size


def get_pip_location(asset: str) -> int:
    """
    Get pip location (decimal places) for different assets.
    
    Args:
        asset: Asset symbol
        
    Returns:
        Pip location (decimal places)
    """
    pip_locations = {
        # Forex pairs (5 decimal places, 4 for pips)
        'EURUSD': 4,
        'GBPUSD': 4,
        'USDJPY': 2,
        'GBPJPY': 2,
        'USDCHF': 4,
        'AUDUSD': 4,
        'NZDUSD': 4,
        'USDCAD': 4,
        # Metals (2 decimal places, 1 for pips)
        'XAUUSD': 1,
        'XAGUSD': 1,
        # Indices (2 decimal places, 1 for pips)
        'US30': 1,
        'NAS100': 1,
        'SPX500': 1,
        'GER40': 1,
    }
    
    return pip_locations.get(asset, 4)  # Default to 4 decimal places


def calculate_pip_value(
    position_size: float,
    pip_location: int,
    price: float
) -> float:
    """
    Calculate pip value for a position.
    
    Args:
        position_size: Position size
        pip_location: Decimal place of pip (e.g., 4 for EURUSD)
        price: Current price
        
    Returns:
        Pip value in account currency
    """
    pip_size = 10 ** (-pip_location)
    pip_value = position_size * pip_size
    return pip_value


def calculate_correlation(df1: pd.Series, df2: pd.Series, period: int = 20) -> float:
    """
    Calculate rolling correlation between two price series.
    
    Args:
        df1: First price series
        df2: Second price series
        period: Rolling period
        
    Returns:
        Correlation coefficient
    """
    return df1.rolling(window=period).corr(df2).iloc[-1]


def resample_ohlcv(
    df: pd.DataFrame,
    timeframe: str
) -> pd.DataFrame:
    """
    Resample OHLCV data to different timeframe.
    
    Args:
        df: DataFrame with OHLCV data
        timeframe: Target timeframe (e.g., '1H', '4H', '1D')
        
    Returns:
        Resampled DataFrame
    """
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    
    agg_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    
    resampled = df.resample(timeframe).agg(agg_dict).dropna()
    return resampled


def detect_outliers(
    series: pd.Series,
    method: str = 'iqr',
    threshold: float = 1.5
) -> pd.Series:
    """
    Detect outliers in a series.
    
    Args:
        series: Data series
        method: Detection method ('iqr' or 'zscore')
        threshold: Threshold for outlier detection
        
    Returns:
        Boolean series indicating outliers
    """
    if method == 'iqr':
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - threshold * IQR
        upper_bound = Q3 + threshold * IQR
        outliers = (series < lower_bound) | (series > upper_bound)
    elif method == 'zscore':
        z_scores = np.abs((series - series.mean()) / series.std())
        outliers = z_scores > threshold
    else:
        raise ValueError(f"Unknown method: {method}")
    
    return outliers


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean OHLCV data by handling outliers and missing values.
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        Cleaned DataFrame
    """
    df = df.copy()
    
    # Handle missing values
    df = df.dropna()
    
    # Ensure OHLC relationships are valid
    df['high'] = df[['open', 'high', 'low', 'close']].max(axis=1)
    df['low'] = df[['open', 'high', 'low', 'close']].min(axis=1)
    
    # Detect and handle outliers
    for column in ['open', 'high', 'low', 'close', 'volume']:
        outliers = detect_outliers(df[column], method='iqr')
        # Replace outliers with rolling median
        df.loc[outliers, column] = df[column].rolling(window=5, min_periods=1).median()
    
    return df


def is_trading_hours(
    dt: datetime,
    asset: str,
    timezone: str = 'UTC'
) -> bool:
    """
    Check if given datetime is within trading hours for asset.
    
    Args:
        dt: Datetime to check
        asset: Asset symbol
        timezone: Timezone string
        
    Returns:
        True if within trading hours
    """
    tz = pytz.timezone(timezone)
    dt = dt.astimezone(tz)
    
    # Forex trading hours (roughly)
    if asset in ['EURUSD', 'GBPJPY', 'XAUUSD']:
        # Sunday 5pm to Friday 5pm EST
        if dt.weekday() == 6:  # Sunday
            return dt.hour >= 17
        elif dt.weekday() == 5:  # Friday
            return dt.hour < 17
        else:  # Monday to Thursday
            return True
    
    return True


def calculate_time_until_next_candle(
    current_time: datetime,
    timeframe: str
) -> timedelta:
    """
    Calculate time until next candle close.
    
    Args:
        current_time: Current datetime
        timeframe: Timeframe string (e.g., '5min', '15min', '1H')
        
    Returns:
        Time until next candle
    """
    timeframe_minutes = {
        '1min': 1,
        '5min': 5,
        '15min': 15,
        '30min': 30,
        '1H': 60,
        '4H': 240,
        '1D': 1440,
    }
    
    minutes = timeframe_minutes.get(timeframe, 15)
    current_minute = current_time.minute
    minutes_to_next = minutes - (current_minute % minutes)
    
    if minutes_to_next == minutes:
        minutes_to_next = 0
    
    return timedelta(minutes=minutes_to_next)


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 5.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying function on failure.
    
    Args:
        max_retries: Maximum number of retries
        delay: Delay between retries in seconds
        exceptions: Exception types to catch
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                    continue
            
            raise last_exception
        
        return wrapper
    return decorator


def validate_ohlcv_data(df: pd.DataFrame) -> bool:
    """
    Validate OHLCV data structure and values.
    
    Args:
        df: DataFrame to validate
        
    Returns:
        True if valid
    """
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    
    # Check required columns
    if not all(col in df.columns for col in required_columns):
        return False
    
    # Check for negative values
    if (df[required_columns] < 0).any().any():
        return False
    
    # Check OHLC relationships
    if (df['high'] < df['low']).any():
        return False
    
    if (df['high'] < df['open']).any() or (df['high'] < df['close']).any():
        return False
    
    if (df['low'] > df['open']).any() or (df['low'] > df['close']).any():
        return False
    
    return True


def merge_timeframes(
    df_main: pd.DataFrame,
    df_filter: pd.DataFrame
) -> pd.DataFrame:
    """
    Merge main and filter timeframes.
    
    Args:
        df_main: Main timeframe data
        df_filter: Filter timeframe data
        
    Returns:
        Merged DataFrame
    """
    # Forward fill filter data to match main timeframe
    df_filter_resampled = df_filter.reindex(df_main.index, method='ffill')
    
    # Merge with suffixes
    merged = pd.concat([df_main, df_filter_resampled.add_suffix('_filter')], axis=1)
    
    return merged
