"""
Helper Functions for Phoenix Protocol Trading System
Common utility functions used across the system.
"""

import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pytz

from config.strategy_params import SYMBOL_METADATA
from config.settings import MARKET_SESSION_TIMEZONE


def ensure_utc(dt: datetime) -> datetime:
    """
    Normalize a datetime to an aware UTC datetime.

    Naive datetimes are interpreted as UTC (the system-wide convention
    used by news windows, data timestamps, and session times).

    Args:
        dt: Datetime (naive or aware)

    Returns:
        Aware datetime in UTC
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=pytz.UTC)
    return dt.astimezone(pytz.UTC)


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
    Calculate position size in MT5 lots based on risk percentage.

    Converts the risk-budgeted position into broker lots using the
    configured contract size, then rounds down to the lot step and clamps
    to the broker's min/max lot. If the computed size falls below the
    minimum lot, 0.0 is returned so the caller refuses to open an
    oversized position instead of silently trading wrong units.

    Args:
        capital: Available capital
        risk_percentage: Risk per trade (0.02 = 2%)
        stop_loss_pct: Stop loss percentage (0.015 = 1.5%)
        entry_price: Entry price
        asset: Asset symbol (must exist in SYMBOL_METADATA)

    Returns:
        Position size in MT5 lots (0.0 if it cannot be sized safely)
    """
    metadata = SYMBOL_METADATA.get(asset)
    if metadata is None:
        raise ValueError(
            f"Unknown asset '{asset}' for position sizing; "
            "add it to config.strategy_params.SYMBOL_METADATA"
        )

    contract_size = metadata['contract_size']
    min_lot = metadata['min_lot']
    max_lot = metadata['max_lot']
    lot_step = metadata['lot_step']

    risk_amount = capital * risk_percentage
    stop_loss_amount = entry_price * stop_loss_pct

    if stop_loss_amount <= 0:
        return 0.0

    # Size in units of the underlying instrument, then convert to lots
    size_units = risk_amount / stop_loss_amount
    size_lots = size_units / contract_size

    # Refuse to trade if the risk budget cannot cover a minimum lot
    if size_lots < min_lot:
        return 0.0

    # Round down to the broker lot step so risk never exceeds the budget
    size_lots = math.floor(size_lots / lot_step) * lot_step

    # Clamp to the broker's maximum lot
    return min(size_lots, max_lot)


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


def generate_sample_data(
    asset: str = "XAUUSD",
    days: int = 30,
    timeframe: str = "M15",
    seed: Optional[int] = None
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data for testing and local backtests.

    Produces a seeded random walk with occasional capitulation drops and
    volume spikes so experiments are reproducible without a broker.

    Args:
        asset: Asset symbol (sets base price level)
        days: Number of days of data
        timeframe: MT5 timeframe (e.g., 'M15', 'H1', 'D1')
        seed: Random seed for reproducibility

    Returns:
        DataFrame with OHLCV columns and tz-aware DatetimeIndex
    """
    base_prices = {
        'XAUUSD': 2400.0,
        'XAGUSD': 28.0,
        'EURUSD': 1.09,
        'GBPUSD': 1.27,
        'USDJPY': 150.0,
        'GBPJPY': 190.0,
        'USDCHF': 0.90,
        'AUDUSD': 0.66,
        'NZDUSD': 0.61,
        'USDCAD': 1.36,
        'US30': 39000.0,
        'NAS100': 19000.0,
        'SPX500': 5200.0,
        'GER40': 17500.0,
    }
    base_price = base_prices.get(asset, 100.0)

    minute_map = {
        'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30,
        'H1': 60, 'H4': 240, 'D1': 1440,
    }
    minutes = minute_map.get(timeframe, 15)
    n_candles = max(100, int(days * 1440 / minutes))

    rng = np.random.default_rng(seed)

    # Random-walk returns with periodic capitulation drops
    returns = rng.normal(0, 0.0015, n_candles)
    step = max(10, int(n_candles * 0.02))
    spike_step = max(step, int(n_candles * 0.06))
    for i in range(step, n_candles, spike_step):
        returns[i] = rng.uniform(-0.05, -0.035)
        if i + 1 < n_candles:
            returns[i + 1] = rng.uniform(0.005, 0.02)

    closes = base_price * np.exp(np.cumsum(returns))

    opens = np.empty(n_candles)
    opens[0] = closes[0]
    opens[1:] = closes[:-1]
    opens = opens + rng.normal(0, 0.001, n_candles) * closes

    highs = np.maximum(opens, closes) * (1 + rng.uniform(0.001, 0.008, n_candles))
    lows = np.minimum(opens, closes) * (1 - rng.uniform(0.001, 0.008, n_candles))

    volumes = rng.integers(800, 1500, n_candles).astype(float)
    for i in range(step, n_candles, spike_step):
        volumes[i] = rng.integers(1800, 2600)

    end_time = datetime.now(pytz.UTC).replace(minute=0, second=0, microsecond=0)
    index = pd.date_range(end=end_time, periods=n_candles, freq=f'{minutes}min', tz=pytz.UTC)

    return pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes,
    }, index=index)


def is_trading_hours(
    dt: datetime,
    asset: str,
    timezone: Optional[str] = None
) -> bool:
    """
    Check if given datetime is within trading hours for asset.
    
    Args:
        dt: Datetime to check
        asset: Asset symbol
        timezone: Timezone string (defaults to MARKET_SESSION_TIMEZONE)
        
    Returns:
        True if within trading hours
    """
    if timezone is None:
        timezone = MARKET_SESSION_TIMEZONE
    tz = pytz.timezone(timezone)
    dt = ensure_utc(dt).astimezone(tz)
    
    # Forex trading hours (roughly), expressed in the session timezone:
    # market opens Sunday at 17:00 and closes Friday at 17:00.
    # weekday(): Monday=0 ... Friday=4, Saturday=5, Sunday=6.
    if asset in ['EURUSD', 'GBPJPY', 'XAUUSD']:
        if dt.weekday() == 6:  # Sunday
            return dt.hour >= 17
        elif dt.weekday() == 5:  # Saturday
            return False
        elif dt.weekday() == 4:  # Friday
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
