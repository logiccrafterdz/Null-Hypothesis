"""
Bad Luck Moment Strategy for Phoenix Protocol Trading System
Implements the main strategy based on detecting capitulation moments.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd

from config.settings import TIMEFRAMES, ASSETS
from config.strategy_params import BAD_LUCK_DETECTOR
from src.strategies.base_strategy import BaseStrategy
from src.api.broker_interface import AccountInfo
from src.core.market_analyzer import BadLuckMoment
from src.utils.logger import get_logger
from src.utils.notifications import get_notification_manager


class BadLuckStrategy(BaseStrategy):
    """
    Bad Luck Moment Strategy.
    Detects market capitulation moments and enters trades with randomness.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize Bad Luck Strategy."""
        super().__init__("Bad Luck Moment", *args, **kwargs)
        self.notification_manager = get_notification_manager()
        self.detected_moments: List[BadLuckMoment] = []
    
    def analyze_market(
        self,
        asset: str,
        timeframe: str
    ) -> Dict[str, Any]:
        """
        Analyze market conditions for bad luck moment detection.
        
        Args:
            asset: Asset symbol
            timeframe: Timeframe to analyze
            
        Returns:
            Dictionary with analysis results
        """
        try:
            # Get latest data
            df = self.data_fetcher.get_latest_data(asset, timeframe, num_candles=100)
            
            if df.empty:
                self.logger.warning(f"No data available for {asset}")
                return {}
            
            # Get filter timeframe data
            filter_timeframe = self.get_filter_timeframe()
            filter_df = self.data_fetcher.get_latest_data(asset, filter_timeframe, num_candles=50)
            
            # Detect bad luck moment
            bad_luck_moment = self.market_analyzer.detect_bad_luck_moment(df, asset)
            
            if not bad_luck_moment:
                return {
                    'asset': asset,
                    'timeframe': timeframe,
                    'has_signal': False,
                    'market_state': self.market_analyzer.analyze_market_state(df, asset),
                    'data': df
                }
            
            # Apply additional filters
            trend_filter_pass = self.market_analyzer.apply_trend_filter(df)
            volatility_filter_pass = self.market_analyzer.apply_volatility_filter(df)
            
            analysis = {
                'asset': asset,
                'timeframe': timeframe,
                'has_signal': True,
                'bad_luck_moment': bad_luck_moment,
                'trend_filter_pass': trend_filter_pass,
                'volatility_filter_pass': volatility_filter_pass,
                'market_state': self.market_analyzer.analyze_market_state(df, asset),
                'data': df,
                'filter_data': filter_df
            }
            
            # Store detected moment
            self.detected_moments.append(bad_luck_moment)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing market for {asset}: {e}")
            return {}
    
    def generate_signal(
        self,
        analysis: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal based on bad luck moment detection.
        
        Args:
            analysis: Market analysis results
            
        Returns:
            Signal dictionary or None if no signal
        """
        if not analysis or not analysis.get('has_signal'):
            return None
        
        bad_luck_moment = analysis['bad_luck_moment']
        
        # Check additional filters
        if not analysis.get('trend_filter_pass', True):
            self.logger.debug("Trend filter failed")
            return None
        
        if not analysis.get('volatility_filter_pass', True):
            self.logger.debug("Volatility filter failed")
            return None
        
        # Apply random decision engine
        should_enter, random_value = self.decision_engine.decide_on_bad_luck_moment(
            bad_luck_moment,
            confidence=1.0
        )
        
        if not should_enter:
            self.logger.info(f"Bad luck moment rejected by random decision: {random_value:.4f}")
            return None
        
        # Generate signal
        current_price = analysis['data']['close'].iloc[-1]
        
        signal = {
            'asset': analysis['asset'],
            'signal_type': 'ENTRY',
            'direction': 'LONG',  # Bad luck moments typically go LONG after drop
            'entry_price': current_price,
            'confidence': 1.0,
            'random_value': random_value,
            'conditions': bad_luck_moment.conditions,
            'timestamp': datetime.now(),
            'strategy': self.name
        }
        
        # Send notification
        self.notification_manager.notify_bad_luck_moment(
            asset=analysis['asset'],
            conditions=bad_luck_moment.conditions,
            accepted=True,
            random_value=random_value
        )
        
        return signal
    
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
        try:
            asset = signal['asset']
            current_price = signal['entry_price']
            
            # Check risk management
            open_positions = self.trade_executor.get_active_trades()
            can_open, reason = self.risk_manager.can_open_trade(
                account_info,
                open_positions,
                asset
            )
            
            if not can_open:
                self.logger.warning(f"Trade blocked by risk management: {reason}")
                
                # Send risk event notification
                self.notification_manager.notify_risk_event(
                    event_type="Trade Blocked",
                    details=reason,
                    severity="WARNING"
                )
                
                return False
            
            # Execute trade
            trade = self.trade_executor.execute_trade(
                asset=asset,
                account_info=account_info,
                current_price=current_price,
                market_conditions=signal
            )
            
            if trade:
                self.logger.info(f"Trade executed successfully: {trade.trade_id}")
                return True
            else:
                self.logger.error("Trade execution failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Error executing signal: {e}")
            return False
    
    def get_main_timeframe(self) -> str:
        """Get main timeframe for strategy."""
        return TIMEFRAMES['main']
    
    def get_filter_timeframe(self) -> str:
        """Get filter timeframe for strategy."""
        return TIMEFRAMES['filter']
    
    def get_detected_moments(self, limit: int = 50) -> List[BadLuckMoment]:
        """
        Get detected bad luck moments.
        
        Args:
            limit: Maximum number to return
            
        Returns:
            List of BadLuckMoment objects
        """
        return self.detected_moments[-limit:]
    
    def clear_detected_moments(self) -> None:
        """Clear all detected moments."""
        self.detected_moments.clear()
        self.market_analyzer.clear_detected_moments()
        self.logger.info("Cleared all detected bad luck moments")
    
    def get_strategy_summary(self) -> Dict[str, Any]:
        """
        Get strategy summary statistics.
        
        Returns:
            Dictionary with strategy summary
        """
        detected_count = len(self.detected_moments)
        accepted_count = sum(1 for m in self.detected_moments if m.accepted)
        acceptance_rate = accepted_count / detected_count if detected_count > 0 else 0.0
        
        return {
            'strategy_name': self.name,
            'detected_moments': detected_count,
            'accepted_moments': accepted_count,
            'acceptance_rate': acceptance_rate,
            'decision_stats': self.decision_engine.get_decision_stats(),
            'trade_statistics': self.trade_executor.get_trade_statistics()
        }
