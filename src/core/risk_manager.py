"""
Risk Manager for Phoenix Protocol Trading System
Implements comprehensive risk management and position sizing.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pytz

from config.strategy_params import RISK_MANAGEMENT, TRADE_MANAGEMENT
from src.api.broker_interface import AccountInfo, Position
from src.utils.logger import get_logger
from src.utils.helpers import calculate_position_size, calculate_correlation

logger = get_logger()


class RiskEventType(Enum):
    """Risk event types."""
    DAILY_LIMIT_REACHED = "daily_limit_reached"
    WEEKLY_LIMIT_REACHED = "weekly_limit_reached"
    MAX_POSITIONS_REACHED = "max_positions_reached"
    COOLDOWN_ACTIVE = "cooldown_active"
    CORRELATION_HIGH = "correlation_high"
    POSITION_SIZE_EXCEEDED = "position_size_exceeded"
    INSUFFICIENT_MARGIN = "insufficient_margin"


@dataclass
class RiskEvent:
    """Represents a risk management event."""
    event_type: RiskEventType
    timestamp: datetime
    details: str
    severity: str = "WARNING"
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary."""
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp,
            'details': self.details,
            'severity': self.severity
        }


@dataclass
class TradeLimits:
    """Current trading limits."""
    daily_loss_used: float = 0.0
    daily_loss_limit: float = 0.0
    weekly_loss_used: float = 0.0
    weekly_loss_limit: float = 0.0
    open_positions: int = 0
    max_positions: int = 0
    consecutive_losses: int = 0
    cooldown_remaining: int = 0
    
    def daily_loss_remaining(self) -> float:
        """Get remaining daily loss allowance."""
        return max(0, self.daily_loss_limit - self.daily_loss_used)
    
    def weekly_loss_remaining(self) -> float:
        """Get remaining weekly loss allowance."""
        return max(0, self.weekly_loss_limit - self.weekly_loss_used)
    
    def positions_remaining(self) -> int:
        """Get remaining position slots."""
        return max(0, self.max_positions - self.open_positions)


class RiskManager:
    """
    Comprehensive risk management system.
    Handles position sizing, loss limits, correlation checks, and cooldowns.
    """
    
    def __init__(self, initial_capital: float = 10000.0):
        """
        Initialize risk manager.
        
        Args:
            initial_capital: Initial trading capital
        """
        self.initial_capital = initial_capital
        self.logger = get_logger()
        
        # Risk parameters
        self.max_daily_loss_pct = RISK_MANAGEMENT['max_daily_loss']
        self.max_weekly_loss_pct = RISK_MANAGEMENT['max_weekly_loss']
        self.max_open_trades = RISK_MANAGEMENT['max_open_trades']
        self.cooldown_after_loss = RISK_MANAGEMENT['cooldown_after_loss']
        self.max_correlation = RISK_MANAGEMENT['max_correlation']
        self.max_position_size_per_asset = RISK_MANAGEMENT['max_position_size_per_asset']
        self.position_size_risk = TRADE_MANAGEMENT['position_size_risk']
        self.stop_loss_pct = TRADE_MANAGEMENT['stop_loss_pct']
        self.take_profit_pct = TRADE_MANAGEMENT['take_profit_pct']
        
        # Trade tracking
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.consecutive_losses = 0
        self.cooldown_trades_remaining = 0
        
        # Risk events
        self.risk_events: List[RiskEvent] = []
        
        # Position correlation matrix
        self.correlation_cache: Dict[str, pd.Series] = {}
        
        # Time tracking
        self.last_reset_date = datetime.now(pytz.UTC).date()
        self.last_week_reset_date = self._get_week_start()
    
    def _get_week_start(self) -> datetime:
        """Get start of current week (Monday)."""
        now = datetime.now(pytz.UTC)
        days_since_monday = now.weekday()
        week_start = now - timedelta(days=days_since_monday)
        return week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    def _check_reset_periods(self) -> None:
        """Check if daily or weekly reset is needed."""
        now = datetime.now(pytz.UTC)
        today = now.date()
        current_week_start = self._get_week_start()
        
        # Daily reset
        if today > self.last_reset_date:
            self.daily_pnl = 0.0
            self.last_reset_date = today
            self.logger.info("Daily PnL reset")
        
        # Weekly reset
        if current_week_start > self.last_week_reset_date:
            self.weekly_pnl = 0.0
            self.consecutive_losses = 0
            self.last_week_reset_date = current_week_start
            self.logger.info("Weekly PnL and consecutive losses reset")
    
    def get_current_capital(self, account_info: AccountInfo) -> float:
        """
        Get current capital based on risk configuration.
        
        Args:
            account_info: Account information
            
        Returns:
            Current capital
        """
        if RISK_MANAGEMENT['risk_based_on'] == 'equity':
            return account_info.equity
        else:
            return account_info.balance
    
    def calculate_position_size(
        self,
        account_info: AccountInfo,
        entry_price: float,
        asset: str = "EURUSD",
        stop_loss_price: Optional[float] = None
    ) -> float:
        """
        Calculate position size in MT5 lots based on risk percentage.

        Args:
            account_info: Account information
            entry_price: Entry price
            asset: Asset symbol for contract metadata
            stop_loss_price: Stop loss price (calculated if not provided)

        Returns:
            Position size in MT5 lots (0.0 if it cannot be sized safely)
        """
        capital = self.get_current_capital(account_info)
        
        # Calculate stop loss if not provided
        if stop_loss_price is None:
            stop_loss_price = entry_price * (1 - self.stop_loss_pct)
        
        # Calculate position size in lots (contract-aware, broker-bounded)
        position_size = calculate_position_size(
            capital=capital,
            risk_percentage=self.position_size_risk,
            stop_loss_pct=self.stop_loss_pct,
            entry_price=entry_price,
            asset=asset
        )
        
        if position_size <= 0:
            return position_size
        
        # Cap position in lot units relative to the risk budget
        # (max_position_size_per_asset = 5% vs position_size_risk = 2%)
        max_lots = position_size * (
            self.max_position_size_per_asset / self.position_size_risk
        )
        if position_size > max_lots:
            position_size = max_lots
            self.logger.debug(f"Position size limited to max: {max_lots}")
        
        return position_size
    
    def check_daily_loss_limit(self, account_info: AccountInfo) -> Tuple[bool, float]:
        """
        Check if daily loss limit has been reached.
        
        Args:
            account_info: Account information
            
        Returns:
            Tuple of (limit_reached, loss_used_pct)
        """
        self._check_reset_periods()
        
        capital = self.get_current_capital(account_info)
        daily_loss_limit = capital * self.max_daily_loss_pct
        loss_used_pct = abs(self.daily_pnl) / capital if self.daily_pnl < 0 else 0.0
        
        limit_reached = self.daily_pnl < -daily_loss_limit
        
        if limit_reached:
            event = RiskEvent(
                event_type=RiskEventType.DAILY_LIMIT_REACHED,
                timestamp=datetime.now(pytz.UTC),
                details=f"Daily loss limit reached: {self.daily_pnl:.2f} / {daily_loss_limit:.2f}",
                severity="CRITICAL"
            )
            self.risk_events.append(event)
            self.logger.warning(f"Daily loss limit reached: {self.daily_pnl:.2f}")
        
        return limit_reached, loss_used_pct
    
    def check_weekly_loss_limit(self, account_info: AccountInfo) -> Tuple[bool, float]:
        """
        Check if weekly loss limit has been reached.
        
        Args:
            account_info: Account information
            
        Returns:
            Tuple of (limit_reached, loss_used_pct)
        """
        self._check_reset_periods()
        
        capital = self.get_current_capital(account_info)
        weekly_loss_limit = capital * self.max_weekly_loss_pct
        loss_used_pct = abs(self.weekly_pnl) / capital if self.weekly_pnl < 0 else 0.0
        
        limit_reached = self.weekly_pnl < -weekly_loss_limit
        
        if limit_reached:
            event = RiskEvent(
                event_type=RiskEventType.WEEKLY_LIMIT_REACHED,
                timestamp=datetime.now(pytz.UTC),
                details=f"Weekly loss limit reached: {self.weekly_pnl:.2f} / {weekly_loss_limit:.2f}",
                severity="CRITICAL"
            )
            self.risk_events.append(event)
            self.logger.warning(f"Weekly loss limit reached: {self.weekly_pnl:.2f}")
        
        return limit_reached, loss_used_pct
    
    def check_max_positions(self, open_positions: List[Position]) -> Tuple[bool, int]:
        """
        Check if maximum number of positions has been reached.
        
        Args:
            open_positions: List of open positions
            
        Returns:
            Tuple of (limit_reached, current_count)
        """
        current_count = len(open_positions)
        limit_reached = current_count >= self.max_open_trades
        
        if limit_reached:
            event = RiskEvent(
                event_type=RiskEventType.MAX_POSITIONS_REACHED,
                timestamp=datetime.now(pytz.UTC),
                details=f"Maximum positions reached: {current_count} / {self.max_open_trades}",
                severity="WARNING"
            )
            self.risk_events.append(event)
            self.logger.warning(f"Maximum positions reached: {current_count}")
        
        return limit_reached, current_count
    
    def check_cooldown(self) -> Tuple[bool, int]:
        """
        Check if cooldown period is active after consecutive losses.
        
        Args:
            
        Returns:
            Tuple of (cooldown_active, trades_remaining)
        """
        cooldown_active = self.cooldown_trades_remaining > 0
        
        if cooldown_active:
            event = RiskEvent(
                event_type=RiskEventType.COOLDOWN_ACTIVE,
                timestamp=datetime.now(pytz.UTC),
                details=f"Cooldown active: {self.cooldown_trades_remaining} trades remaining",
                severity="INFO"
            )
            self.risk_events.append(event)
            self.logger.debug(f"Cooldown active: {self.cooldown_trades_remaining} trades")
        
        return cooldown_active, self.cooldown_trades_remaining
    
    def check_correlation(
        self,
        new_asset: str,
        open_positions: List[Position],
        price_data: Dict[str, pd.Series]
    ) -> Tuple[bool, float]:
        """
        Check if new asset is too correlated with existing positions.
        
        Args:
            new_asset: New asset symbol
            open_positions: List of open positions
            price_data: Dictionary of price data for correlation calculation
            
        Returns:
            Tuple of (correlation_too_high, max_correlation)
        """
        if not open_positions:
            return False, 0.0
        
        if new_asset not in price_data:
            self.logger.warning(f"No price data for correlation check: {new_asset}")
            return False, 0.0
        
        new_prices = price_data[new_asset]
        max_correlation = 0.0
        
        for position in open_positions:
            asset = position.symbol
            if asset not in price_data:
                continue
            
            existing_prices = price_data[asset]
            
            # Calculate correlation
            try:
                correlation = calculate_correlation(new_prices, existing_prices, period=20)
                
                if not np.isnan(correlation) and abs(correlation) > max_correlation:
                    max_correlation = abs(correlation)
            except Exception as e:
                self.logger.error(f"Error calculating correlation: {e}")
        
        correlation_too_high = max_correlation > self.max_correlation
        
        if correlation_too_high:
            event = RiskEvent(
                event_type=RiskEventType.CORRELATION_HIGH,
                timestamp=datetime.now(pytz.UTC),
                details=f"High correlation detected: {new_asset} with max {max_correlation:.2f}",
                severity="WARNING"
            )
            self.risk_events.append(event)
            self.logger.warning(f"High correlation: {max_correlation:.2f}")
        
        return correlation_too_high, max_correlation
    
    def can_open_trade(
        self,
        account_info: AccountInfo,
        open_positions: List[Position],
        new_asset: str,
        price_data: Optional[Dict[str, pd.Series]] = None
    ) -> Tuple[bool, str]:
        """
        Check if a new trade can be opened based on all risk rules.
        
        Args:
            account_info: Account information
            open_positions: List of open positions
            new_asset: New asset symbol
            price_data: Price data for correlation check
            
        Returns:
            Tuple of (can_open, reason)
        """
        # Check daily loss limit
        daily_limit_reached, _ = self.check_daily_loss_limit(account_info)
        if daily_limit_reached:
            return False, "Daily loss limit reached"
        
        # Check weekly loss limit
        weekly_limit_reached, _ = self.check_weekly_loss_limit(account_info)
        if weekly_limit_reached:
            return False, "Weekly loss limit reached"
        
        # Check max positions
        max_positions_reached, _ = self.check_max_positions(open_positions)
        if max_positions_reached:
            return False, "Maximum positions reached"
        
        # Check cooldown
        cooldown_active, _ = self.check_cooldown()
        if cooldown_active:
            # Each blocked opportunity depletes the cooldown so a single
            # loss cannot block trading forever.
            self.update_cooldown()
            return False, "Cooldown period active"
        
        # Check correlation if price data provided
        if price_data:
            correlation_too_high, _ = self.check_correlation(new_asset, open_positions, price_data)
            if correlation_too_high:
                return False, "Asset too correlated with existing positions"
        
        return True, "All risk checks passed"
    
    def record_trade_pnl(self, pnl: float) -> None:
        """
        Record trade PnL and update risk metrics.
        
        Args:
            pnl: Trade profit/loss
        """
        self.daily_pnl += pnl
        self.weekly_pnl += pnl
        
        if pnl < 0:
            self.consecutive_losses += 1
            self.cooldown_trades_remaining = self.cooldown_after_loss
            self.logger.info(f"Loss recorded. Consecutive losses: {self.consecutive_losses}")
        else:
            self.consecutive_losses = 0
            self.cooldown_trades_remaining = 0
            self.logger.info(f"Profit recorded. Consecutive losses reset")
    
    def update_cooldown(self) -> None:
        """Decrement cooldown counter after a trade is skipped."""
        if self.cooldown_trades_remaining > 0:
            self.cooldown_trades_remaining -= 1
            self.logger.debug(f"Cooldown decremented: {self.cooldown_trades_remaining} remaining")
    
    def get_trade_limits(self, account_info: AccountInfo) -> TradeLimits:
        """
        Get current trade limits.
        
        Args:
            account_info: Account information
            
        Returns:
            TradeLimits object
        """
        capital = self.get_current_capital(account_info)
        
        return TradeLimits(
            daily_loss_used=abs(self.daily_pnl) if self.daily_pnl < 0 else 0.0,
            daily_loss_limit=capital * self.max_daily_loss_pct,
            weekly_loss_used=abs(self.weekly_pnl) if self.weekly_pnl < 0 else 0.0,
            weekly_loss_limit=capital * self.max_weekly_loss_pct,
            open_positions=0,  # Will be updated by caller
            max_positions=self.max_open_trades,
            consecutive_losses=self.consecutive_losses,
            cooldown_remaining=self.cooldown_trades_remaining
        )
    
    def get_risk_events(self, limit: int = 50) -> List[RiskEvent]:
        """
        Get recent risk events.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of RiskEvent objects
        """
        return self.risk_events[-limit:]
    
    def clear_risk_events(self) -> None:
        """Clear all risk events."""
        self.risk_events.clear()
        self.logger.info("Risk events cleared")
    
    def get_risk_summary(self, account_info: AccountInfo) -> Dict[str, any]:
        """
        Get risk management summary.
        
        Args:
            account_info: Account information
            
        Returns:
            Dictionary with risk summary
        """
        capital = self.get_current_capital(account_info)
        
        return {
            'capital': capital,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': self.daily_pnl / capital,
            'daily_loss_limit': capital * self.max_daily_loss_pct,
            'daily_loss_remaining': self.get_trade_limits(account_info).daily_loss_remaining(),
            'weekly_pnl': self.weekly_pnl,
            'weekly_pnl_pct': self.weekly_pnl / capital,
            'weekly_loss_limit': capital * self.max_weekly_loss_pct,
            'weekly_loss_remaining': self.get_trade_limits(account_info).weekly_loss_remaining(),
            'consecutive_losses': self.consecutive_losses,
            'cooldown_remaining': self.cooldown_trades_remaining,
            'max_positions': self.max_open_trades,
            'position_size_risk': self.position_size_risk,
            'risk_events_count': len(self.risk_events)
        }
