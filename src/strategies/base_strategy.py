"""
Base Strategy Class for Null Hypothesis Trading System
Provides abstract base class for all trading strategies.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd

from src.api.broker_interface import UnifiedBroker, AccountInfo
from src.core.data_fetcher import DataFetcher
from src.core.market_analyzer import MarketAnalyzer
from src.core.decision_engine import DecisionEngine
from src.core.risk_manager import RiskManager
from src.core.trade_executor import TradeExecutor
from src.utils.logger import get_logger


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.
    All strategies should inherit from this class.
    """
    
    def __init__(
        self,
        name: str,
        unified_broker: UnifiedBroker,
        data_fetcher: DataFetcher,
        risk_manager: RiskManager,
        trade_executor: TradeExecutor
    ):
        """
        Initialize base strategy.
        
        Args:
            name: Strategy name
            unified_broker: Unified broker instance
            data_fetcher: Data fetcher instance
            risk_manager: Risk manager instance
            trade_executor: Trade executor instance
        """
        self.name = name
        self.unified_broker = unified_broker
        self.data_fetcher = data_fetcher
        self.risk_manager = risk_manager
        self.trade_executor = trade_executor
        
        self.logger = get_logger()
        self.market_analyzer = MarketAnalyzer()
        self.decision_engine = DecisionEngine()
        
        self.enabled = True
        self.last_execution_time = None
    
    @abstractmethod
    def analyze_market(
        self,
        asset: str,
        timeframe: str
    ) -> Dict[str, Any]:
        """
        Analyze market conditions for an asset.
        
        Args:
            asset: Asset symbol
            timeframe: Timeframe to analyze
            
        Returns:
            Dictionary with analysis results
        """
        pass
    
    @abstractmethod
    def generate_signal(
        self,
        analysis: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal based on analysis.
        
        Args:
            analysis: Market analysis results
            
        Returns:
            Signal dictionary or None if no signal
        """
        pass
    
    @abstractmethod
    def execute_signal(
        self,
        signal: Dict[str, Any],
        account_info: AccountInfo
    ) -> bool:
        """
        Execute trading signal.
        
        Args:
            signal: Trading signal
            account_info: Account information
            
        Returns:
            True if execution successful
        """
        pass
    
    def process_asset(
        self,
        asset: str,
        account_info: AccountInfo
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single asset through the strategy pipeline.
        
        Args:
            asset: Asset symbol
            account_info: Account information
            
        Returns:
            Signal dictionary or None
        """
        if not self.enabled:
            self.logger.debug(f"Strategy {self.name} is disabled")
            return None
        
        try:
            # Analyze market
            analysis = self.analyze_market(asset, self.get_main_timeframe())
            
            if not analysis:
                self.logger.debug(f"No analysis results for {asset}")
                return None
            
            # Generate signal
            signal = self.generate_signal(analysis)
            
            if not signal:
                self.logger.debug(f"No signal generated for {asset}")
                return None
            
            # Execute signal
            success = self.execute_signal(signal, account_info)
            
            if success:
                self.logger.info(f"Signal executed for {asset}: {signal}")
                return signal
            else:
                self.logger.warning(f"Signal execution failed for {asset}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error processing {asset}: {e}")
            return None
    
    def run_cycle(
        self,
        assets: List[str],
        account_info: AccountInfo
    ) -> Dict[str, Any]:
        """
        Run a complete strategy cycle for all assets.
        
        Args:
            assets: List of assets to process
            account_info: Account information
            
        Returns:
            Dictionary with cycle results
        """
        self.last_execution_time = datetime.now()
        
        results = {
            'timestamp': self.last_execution_time,
            'strategy': self.name,
            'assets_processed': 0,
            'signals_generated': 0,
            'signals_executed': 0,
            'errors': 0,
            'asset_results': {}
        }
        
        for asset in assets:
            try:
                signal = self.process_asset(asset, account_info)
                
                results['assets_processed'] += 1
                
                if signal:
                    results['signals_generated'] += 1
                    results['signals_executed'] += 1
                    results['asset_results'][asset] = {
                        'status': 'success',
                        'signal': signal
                    }
                else:
                    results['asset_results'][asset] = {
                        'status': 'no_signal'
                    }
                    
            except Exception as e:
                results['errors'] += 1
                results['asset_results'][asset] = {
                    'status': 'error',
                    'error': str(e)
                }
                self.logger.error(f"Error in cycle for {asset}: {e}")
        
        return results
    
    def get_main_timeframe(self) -> str:
        """
        Get main timeframe for strategy.
        
        Returns:
            Timeframe string
        """
        return "M15"
    
    def get_filter_timeframe(self) -> str:
        """
        Get filter timeframe for strategy.
        
        Returns:
            Timeframe string
        """
        return "H1"
    
    def enable(self) -> None:
        """Enable strategy."""
        self.enabled = True
        self.logger.info(f"Strategy {self.name} enabled")
    
    def disable(self) -> None:
        """Disable strategy."""
        self.enabled = False
        self.logger.info(f"Strategy {self.name} disabled")
    
    def is_enabled(self) -> bool:
        """
        Check if strategy is enabled.
        
        Returns:
            True if enabled
        """
        return self.enabled
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get strategy status.
        
        Returns:
            Dictionary with status information
        """
        return {
            'name': self.name,
            'enabled': self.enabled,
            'last_execution': self.last_execution_time,
            'main_timeframe': self.get_main_timeframe(),
            'filter_timeframe': self.get_filter_timeframe()
        }
    
    def validate_parameters(self) -> bool:
        """
        Validate strategy parameters.
        
        Returns:
            True if parameters are valid
        """
        return True
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get strategy performance metrics.
        
        Returns:
            Dictionary with performance metrics
        """
        trade_stats = self.trade_executor.get_trade_statistics()
        
        return {
            'strategy_name': self.name,
            'trade_statistics': trade_stats,
            'decision_stats': self.decision_engine.get_decision_stats(),
            'risk_summary': self.risk_manager.get_risk_summary(
                self.unified_broker.get_broker_for_asset(list(self.data_fetcher.asset_mapping.keys())[0]).get_account_info() if self.unified_broker.is_connected() else None
            )
        }
