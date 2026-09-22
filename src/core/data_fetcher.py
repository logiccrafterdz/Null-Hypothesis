"""
Data Fetcher for Phoenix Protocol Trading System
Handles multi-source data fetching with local storage and caching.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import pytz

from config.settings import (
    DATA_DIR,
    DATA_SOURCE,
    DATA_RETENTION_DAYS,
    ASSETS,
    TIMEFRAMES
)
from src.api.broker_interface import UnifiedBroker
from src.utils.logger import get_logger
from src.utils.helpers import clean_data, resample_ohlcv, validate_ohlcv_data

logger = get_logger()


class DataFetcher:
    """Multi-source data fetcher with local storage and caching."""
    
    def __init__(self, unified_broker: UnifiedBroker):
        """
        Initialize data fetcher.
        
        Args:
            unified_broker: Unified broker instance
        """
        self.unified_broker = unified_broker
        self.data_dir = DATA_DIR
        self.raw_dir = self.data_dir / "raw"
        self.processed_dir = self.data_dir / "processed"
        self.cache_dir = self.data_dir / "cache"
        
        # Create directories
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = get_logger()
        self.data_cache: Dict[str, pd.DataFrame] = {}
    
    def get_data_path(self, symbol: str, timeframe: str, data_type: str = "raw") -> Path:
        """
        Get file path for cached data.
        
        Args:
            symbol: Asset symbol
            timeframe: Timeframe
            data_type: Type of data (raw or processed)
            
        Returns:
            Path to data file
        """
        dir_path = self.raw_dir if data_type == "raw" else self.processed_dir
        filename = f"{symbol}_{timeframe}.parquet"
        return dir_path / filename
    
    def load_cached_data(
        self,
        symbol: str,
        timeframe: str,
        data_type: str = "raw"
    ) -> Optional[pd.DataFrame]:
        """
        Load cached data from disk.
        
        Args:
            symbol: Asset symbol
            timeframe: Timeframe
            data_type: Type of data (raw or processed)
            
        Returns:
            DataFrame or None if not found
        """
        try:
            file_path = self.get_data_path(symbol, timeframe, data_type)
            
            if not file_path.exists():
                return None
            
            df = pd.read_parquet(file_path)
            
            # Check if data is too old
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, pytz.UTC)
            age_days = (datetime.now(pytz.UTC) - file_mtime).days
            
            if age_days > DATA_RETENTION_DAYS:
                self.logger.info(f"Cached data for {symbol} {timeframe} is too old ({age_days} days)")
                return None
            
            self.logger.debug(f"Loaded cached data for {symbol} {timeframe}")
            return df
            
        except Exception as e:
            self.logger.error(f"Error loading cached data: {e}")
            return None
    
    def save_cached_data(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        data_type: str = "raw"
    ) -> bool:
        """
        Save data to cache.
        
        Args:
            df: DataFrame to save
            symbol: Asset symbol
            timeframe: Timeframe
            data_type: Type of data (raw or processed)
            
        Returns:
            True if successful
        """
        try:
            file_path = self.get_data_path(symbol, timeframe, data_type)
            df.to_parquet(file_path, index=True)
            self.logger.debug(f"Saved cached data for {symbol} {timeframe}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving cached data: {e}")
            return False
    
    def fetch_live_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Fetch live data from broker.
        
        Args:
            symbol: Asset symbol
            timeframe: Timeframe
            start_date: Start date
            end_date: End date
            
        Returns:
            DataFrame with OHLCV data
        """
        broker = self.unified_broker.get_broker_for_asset(symbol)
        
        if broker is None:
            raise ValueError(f"No broker configured for {symbol}")
        
        try:
            df = broker.get_historical_data(symbol, timeframe, start_date, end_date)
            
            if df.empty:
                self.logger.warning(f"No data retrieved for {symbol} {timeframe}")
                return pd.DataFrame()
            
            # Validate data
            if not validate_ohlcv_data(df):
                self.logger.warning(f"Invalid OHLCV data for {symbol} {timeframe}")
                return pd.DataFrame()
            
            # Clean data
            df = clean_data(df)
            
            self.logger.info(f"Fetched {len(df)} candles for {symbol} {timeframe}")
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching live data: {e}")
            raise
    
    def get_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Get data with automatic caching and update logic.
        
        Args:
            symbol: Asset symbol
            timeframe: Timeframe
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to now)
            force_refresh: Force refresh from live source
            
        Returns:
            DataFrame with OHLCV data
        """
        # Set default dates
        if end_date is None:
            end_date = datetime.now(pytz.UTC)
        if start_date is None:
            start_date = end_date - timedelta(days=30)
        
        # Local data source: read local fixtures only, never contact the broker.
        if DATA_SOURCE == "local":
            cached_df = self.load_cached_data(symbol, timeframe, "raw")
            if cached_df is not None and not cached_df.empty:
                filtered_df = cached_df[
                    (cached_df.index >= start_date) & (cached_df.index <= end_date)
                ]
                if not filtered_df.empty:
                    self.logger.info(f"Using cached data for {symbol} {timeframe}")
                    return filtered_df

            # Fail loudly instead of silently returning empty data that
            # silently cripples backtests/live runs.
            raise ValueError(
                f"DATA_SOURCE='local' has no cached data for {symbol} {timeframe} "
                f"covering {start_date} to {end_date}. Generate fixtures with "
                f"'python main.py --generate-sample-data' or place a file at "
                f"{self.get_data_path(symbol, timeframe, 'raw')}."
            )
        
        # Try to load cached data
        if not force_refresh and DATA_SOURCE != "live":
            cached_df = self.load_cached_data(symbol, timeframe, "raw")
            
            if cached_df is not None and not cached_df.empty:
                # Check if we need to update
                last_cached_date = cached_df.index.max()
                if last_cached_date >= start_date:
                    # Filter to requested range
                    filtered_df = cached_df[(cached_df.index >= start_date) & (cached_df.index <= end_date)]
                    
                    if not filtered_df.empty:
                        self.logger.info(f"Using cached data for {symbol} {timeframe}")
                        return filtered_df
        
        # Fetch fresh data
        if DATA_SOURCE in ["live", "hybrid"]:
            try:
                df = self.fetch_live_data(symbol, timeframe, start_date, end_date)
                
                if not df.empty:
                    # Save to cache
                    self.save_cached_data(df, symbol, timeframe, "raw")
                    return df
            except Exception as e:
                self.logger.error(f"Failed to fetch live data: {e}")
        
        # Fallback to cached data
        cached_df = self.load_cached_data(symbol, timeframe, "raw")
        if cached_df is not None and not cached_df.empty:
            self.logger.warning(f"Using cached data as fallback for {symbol} {timeframe}")
            filtered_df = cached_df[(cached_df.index >= start_date) & (cached_df.index <= end_date)]
            return filtered_df
        
        self.logger.error(f"No data available for {symbol} {timeframe}")
        return pd.DataFrame()
    
    def get_multi_timeframe_data(
        self,
        symbol: str,
        timeframes: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        force_refresh: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """
        Get data for multiple timeframes.
        
        Args:
            symbol: Asset symbol
            timeframes: List of timeframes (defaults to TIMEFRAMES values)
            start_date: Start date
            end_date: End date
            force_refresh: Force refresh from live source
            
        Returns:
            Dictionary mapping timeframe to DataFrame
        """
        if timeframes is None:
            timeframes = list(TIMEFRAMES.values())
        
        data_dict = {}
        
        for tf in timeframes:
            try:
                df = self.get_data(symbol, tf, start_date, end_date, force_refresh)
                if not df.empty:
                    data_dict[tf] = df
            except Exception as e:
                self.logger.error(f"Error getting data for {symbol} {tf}: {e}")
        
        return data_dict
    
    def update_data_cache(self, symbols: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        Update data cache for all or specific symbols.
        
        Args:
            symbols: List of symbols to update (defaults to all assets)
            
        Returns:
            Dictionary mapping symbol to success status
        """
        if symbols is None:
            symbols = list(ASSETS.keys())
        
        results = {}
        end_date = datetime.now(pytz.UTC)
        start_date = end_date - timedelta(days=30)
        
        for symbol in symbols:
            try:
                df = self.get_data(symbol, TIMEFRAMES['main'], start_date, end_date, force_refresh=True)
                results[symbol] = not df.empty
            except Exception as e:
                self.logger.error(f"Error updating cache for {symbol}: {e}")
                results[symbol] = False
        
        return results
    
    def resample_data(
        self,
        df: pd.DataFrame,
        target_timeframe: str
    ) -> pd.DataFrame:
        """
        Resample data to different timeframe.
        
        Args:
            df: Source DataFrame
            target_timeframe: Target timeframe
            
        Returns:
            Resampled DataFrame
        """
        try:
            return resample_ohlcv(df, target_timeframe)
        except Exception as e:
            self.logger.error(f"Error resampling data: {e}")
            return df
    
    def merge_timeframes(
        self,
        main_df: pd.DataFrame,
        filter_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge main and filter timeframes.
        
        Args:
            main_df: Main timeframe data
            filter_df: Filter timeframe data
            
        Returns:
            Merged DataFrame
        """
        try:
            return pd.merge(
                main_df,
                filter_df,
                left_index=True,
                right_index=True,
                how='left',
                suffixes=('', '_filter')
            )
        except Exception as e:
            self.logger.error(f"Error merging timeframes: {e}")
            return main_df
    
    def get_latest_data(
        self,
        symbol: str,
        timeframe: str,
        num_candles: int = 100
    ) -> pd.DataFrame:
        """
        Get latest N candles for a symbol.
        
        Args:
            symbol: Asset symbol
            timeframe: Timeframe
            num_candles: Number of candles to retrieve
            
        Returns:
            DataFrame with latest candles
        """
        end_date = datetime.now(pytz.UTC)
        
        # Estimate start date based on timeframe
        timeframe_minutes = {
            'M1': 1,
            'M5': 5,
            'M15': 15,
            'M30': 30,
            'H1': 60,
            'H4': 240,
            'D1': 1440,
        }
        
        minutes = timeframe_minutes.get(timeframe, 15)
        # Pad the window so the filtered range reliably holds at least
        # num_candles bars (a bare num_candles window yields fewer).
        margin = min(20, num_candles)
        start_date = end_date - timedelta(minutes=minutes * (num_candles + margin))
        
        df = self.get_data(symbol, timeframe, start_date, end_date)
        
        return df.tail(num_candles)
    
    def clear_cache(self, symbol: Optional[str] = None) -> bool:
        """
        Clear cached data.
        
        Args:
            symbol: Specific symbol to clear (clears all if None)
            
        Returns:
            True if successful
        """
        try:
            if symbol:
                for tf in TIMEFRAMES.values():
                    file_path = self.get_data_path(symbol, tf, "raw")
                    if file_path.exists():
                        file_path.unlink()
                    file_path = self.get_data_path(symbol, tf, "processed")
                    if file_path.exists():
                        file_path.unlink()
            else:
                # Clear all cached files
                for file_path in self.raw_dir.glob("*.parquet"):
                    file_path.unlink()
                for file_path in self.processed_dir.glob("*.parquet"):
                    file_path.unlink()
            
            self.logger.info(f"Cleared cache for {symbol if symbol else 'all symbols'}")
            return True
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            return False
    
    def get_cache_info(self) -> Dict[str, Dict[str, any]]:
        """
        Get information about cached data.
        
        Returns:
            Dictionary with cache information
        """
        cache_info = {}
        
        for file_path in self.raw_dir.glob("*.parquet"):
            try:
                symbol, timeframe = file_path.stem.split('_')
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime, pytz.UTC)
                size = file_path.stat().st_size
                
                cache_info[f"{symbol}_{timeframe}"] = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'last_updated': mtime,
                    'size_bytes': size,
                    'size_mb': size / (1024 * 1024)
                }
            except Exception as e:
                self.logger.error(f"Error getting cache info for {file_path}: {e}")
        
        return cache_info
