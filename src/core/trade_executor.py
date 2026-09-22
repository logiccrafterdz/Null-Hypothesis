"""
Trade Executor for Phoenix Protocol Trading System
Handles trade execution, order management, and position monitoring.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pytz

from config.strategy_params import TRADE_MANAGEMENT
from src.api.broker_interface import (
    UnifiedBroker,
    Order,
    AccountInfo
)
from src.core.risk_manager import RiskManager
from src.utils.logger import get_logger
from src.utils.notifications import get_notification_manager

logger = get_logger()


class TradeStatus(Enum):
    """Trade status types."""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class Trade:
    """Represents a complete trade from entry to exit."""
    trade_id: str
    asset: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    size: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    status: TradeStatus = TradeStatus.PENDING
    exit_reason: str = ""
    max_profit: float = 0.0
    max_loss: float = 0.0
    candles_since_entry: int = 0
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary."""
        return {
            'trade_id': self.trade_id,
            'asset': self.asset,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'size': self.size,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'entry_time': self.entry_time,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            'status': self.status.value,
            'exit_reason': self.exit_reason,
            'max_profit': self.max_profit,
            'max_loss': self.max_loss,
            'candles_since_entry': self.candles_since_entry
        }


class TradeExecutor:
    """
    Trade execution and management system.
    Handles order placement, position monitoring, and trade lifecycle.
    """
    
    def __init__(
        self,
        unified_broker: UnifiedBroker,
        risk_manager: RiskManager
    ):
        """
        Initialize trade executor.
        
        Args:
            unified_broker: Unified broker instance
            risk_manager: Risk manager instance
        """
        self.unified_broker = unified_broker
        self.risk_manager = risk_manager
        self.logger = get_logger()
        self.notification_manager = get_notification_manager()
        
        # Trade tracking
        self.active_trades: Dict[str, Trade] = {}
        self.trade_history: List[Trade] = []
        self.trade_counter = 0
        
        # Trade management parameters
        self.stop_loss_pct = TRADE_MANAGEMENT['stop_loss_pct']
        self.take_profit_pct = TRADE_MANAGEMENT['take_profit_pct']
        self.trailing_stop = TRADE_MANAGEMENT['trailing_stop']
        self.trailing_activation_pct = TRADE_MANAGEMENT['trailing_activation_pct']
        self.trailing_distance_pct = TRADE_MANAGEMENT['trailing_distance_pct']
        self.max_duration_candles = TRADE_MANAGEMENT['max_duration_candles']
        self.order_type = TRADE_MANAGEMENT['order_type']
    
    def _generate_trade_id(self) -> str:
        """Generate unique trade ID."""
        self.trade_counter += 1
        timestamp = datetime.now(pytz.UTC).strftime('%Y%m%d%H%M%S')
        return f"TRD{timestamp}_{self.trade_counter:04d}"
    
    def calculate_stop_loss(self, entry_price: float, direction: str) -> float:
        """
        Calculate stop loss price.
        
        Args:
            entry_price: Entry price
            direction: Trade direction ('LONG' or 'SHORT')
            
        Returns:
            Stop loss price
        """
        if direction == 'LONG':
            return entry_price * (1 - self.stop_loss_pct)
        else:
            return entry_price * (1 + self.stop_loss_pct)
    
    def calculate_take_profit(self, entry_price: float, direction: str) -> float:
        """
        Calculate take profit price.
        
        Args:
            entry_price: Entry price
            direction: Trade direction ('LONG' or 'SHORT')
            
        Returns:
            Take profit price
        """
        if direction == 'LONG':
            return entry_price * (1 + self.take_profit_pct)
        else:
            return entry_price * (1 - self.take_profit_pct)
    
    def determine_direction(self, market_conditions: Dict[str, any]) -> str:
        """
        Determine trade direction based on market conditions.
        
        Args:
            market_conditions: Market analysis results
            
        Returns:
            Trade direction ('LONG' or 'SHORT')
        """
        # For bad luck moment strategy, we typically go LONG after a drop
        # This can be enhanced with additional logic
        return 'LONG'
    
    def execute_trade(
        self,
        asset: str,
        account_info: AccountInfo,
        current_price: float,
        market_conditions: Dict[str, any]
    ) -> Optional[Trade]:
        """
        Execute a trade based on market conditions.
        
        Args:
            asset: Asset symbol
            account_info: Account information
            current_price: Current price
            market_conditions: Market analysis results
            
        Returns:
            Trade object or None if execution failed
        """
        try:
            # Get broker for asset
            broker = self.unified_broker.get_broker_for_asset(asset)
            if broker is None:
                self.logger.error(f"No broker configured for {asset}")
                return None
            
            # Determine direction
            direction = self.determine_direction(market_conditions)
            
            # Calculate position size
            position_size = self.risk_manager.calculate_position_size(
                account_info,
                current_price,
                asset
            )
            
            if position_size <= 0:
                self.logger.error(f"Invalid position size: {position_size}")
                return None
            
            # Calculate stop loss and take profit
            stop_loss = self.calculate_stop_loss(current_price, direction)
            take_profit = self.calculate_take_profit(current_price, direction)
            
            # Create order
            order = Order(
                order_id=self._generate_trade_id(),
                symbol=asset,
                direction='BUY' if direction == 'LONG' else 'SELL',
                order_type=self.order_type.upper(),
                price=current_price,
                size=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                status='PENDING',
                timestamp=datetime.now(pytz.UTC)
            )
            
            # Place order
            order_id = broker.place_order(order)
            
            if not order_id:
                self.logger.error("Order placement failed")
                return None
            
            # Create trade record
            trade = Trade(
                trade_id=order_id,
                asset=asset,
                direction=direction,
                entry_price=current_price,
                size=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                entry_time=datetime.now(pytz.UTC),
                status=TradeStatus.OPEN
            )
            
            self.active_trades[order_id] = trade
            self.logger.info(f"Trade executed: {order_id} {asset} {direction} @ {current_price}")
            
            # Send notification
            self.notification_manager.notify_trade_entry(
                asset=asset,
                direction=direction,
                entry_price=current_price,
                size=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            return trade
            
        except Exception as e:
            self.logger.error(f"Error executing trade: {e}")
            return None
    
    def monitor_positions(self) -> List[Tuple[Trade, str]]:
        """
        Monitor open positions and manage trailing stops.
        
        Returns:
            List of (trade, reason) tuples that need to be closed
        """
        trades_to_close = []
        
        for trade_id, trade in self.active_trades.items():
            try:
                broker = self.unified_broker.get_broker_for_asset(trade.asset)
                if broker is None:
                    continue
                
                # Get current price
                current_price = broker.get_current_price(trade.asset)
                
                # Calculate current PnL
                if trade.direction == 'LONG':
                    pnl_pct = (current_price - trade.entry_price) / trade.entry_price
                else:
                    pnl_pct = (trade.entry_price - current_price) / trade.entry_price
                
                trade.pnl = trade.size * (current_price - trade.entry_price)
                trade.pnl_pct = pnl_pct
                
                # Update max profit/loss
                if pnl_pct > trade.max_profit:
                    trade.max_profit = pnl_pct
                if pnl_pct < trade.max_loss:
                    trade.max_loss = pnl_pct
                
                # Check stop loss
                if trade.direction == 'LONG':
                    if current_price <= trade.stop_loss:
                        trades_to_close.append((trade, "Stop Loss Hit"))
                else:
                    if current_price >= trade.stop_loss:
                        trades_to_close.append((trade, "Stop Loss Hit"))
                
                # Check take profit
                if trade.direction == 'LONG':
                    if current_price >= trade.take_profit:
                        trades_to_close.append((trade, "Take Profit Hit"))
                else:
                    if current_price <= trade.take_profit:
                        trades_to_close.append((trade, "Take Profit Hit"))
                
                # Trailing stop logic
                if self.trailing_stop and pnl_pct >= self.trailing_activation_pct:
                    if trade.direction == 'LONG':
                        new_stop = current_price * (1 - self.trailing_distance_pct)
                        if new_stop > trade.stop_loss:
                            trade.stop_loss = new_stop
                            broker.modify_order(trade_id, stop_loss=new_stop)
                            self.logger.debug(f"Trailing stop updated: {new_stop}")
                    else:
                        new_stop = current_price * (1 + self.trailing_distance_pct)
                        if new_stop < trade.stop_loss:
                            trade.stop_loss = new_stop
                            broker.modify_order(trade_id, stop_loss=new_stop)
                            self.logger.debug(f"Trailing stop updated: {new_stop}")
                
                # Max duration check
                trade.candles_since_entry += 1
                if trade.candles_since_entry >= self.max_duration_candles:
                    trades_to_close.append((trade, "MAX_DURATION_REACHED"))
                    self.logger.info(f"Trade {trade_id} reached max duration ({self.max_duration_candles} candles)")
                
            except Exception as e:
                self.logger.error(f"Error monitoring position {trade_id}: {e}")
        
        return trades_to_close
    
    def close_trade(
        self,
        trade: Trade,
        exit_price: float,
        exit_reason: str
    ) -> bool:
        """
        Close a trade.
        
        Args:
            trade: Trade to close
            exit_price: Exit price
            exit_reason: Reason for closing
            
        Returns:
            True if successful
        """
        try:
            broker = self.unified_broker.get_broker_for_asset(trade.asset)
            if broker is None:
                self.logger.error(f"No broker configured for {trade.asset}")
                return False
            
            # Close position
            success = broker.close_position(trade.trade_id)
            
            if not success:
                self.logger.error(f"Failed to close trade {trade.trade_id}")
                return False
            
            # Update trade record
            trade.exit_price = exit_price
            trade.exit_time = datetime.now(pytz.UTC)
            trade.status = TradeStatus.CLOSED
            trade.exit_reason = exit_reason
            
            # Recalculate final PnL
            if trade.direction == 'LONG':
                trade.pnl = trade.size * (exit_price - trade.entry_price)
            else:
                trade.pnl = trade.size * (trade.entry_price - exit_price)
            
            trade.pnl_pct = trade.pnl / (trade.entry_price * trade.size)
            
            # Move to history
            self.trade_history.append(trade)
            del self.active_trades[trade.trade_id]
            
            # Record PnL in risk manager
            self.risk_manager.record_trade_pnl(trade.pnl)
            
            # Send notification
            self.notification_manager.notify_trade_exit(
                asset=trade.asset,
                exit_price=exit_price,
                pnl=trade.pnl,
                pnl_pct=trade.pnl_pct,
                reason=exit_reason
            )
            
            self.logger.info(f"Trade closed: {trade.trade_id} PnL: {trade.pnl:.2f} ({trade.pnl_pct:.2%})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing trade: {e}")
            return False
    
    def close_all_trades(self, reason: str = "Manual Close") -> int:
        """
        Close all active trades.
        
        Args:
            reason: Reason for closing
            
        Returns:
            Number of trades closed
        """
        closed_count = 0
        
        for trade_id, trade in list(self.active_trades.items()):
            try:
                broker = self.unified_broker.get_broker_for_asset(trade.asset)
                if broker is None:
                    continue
                
                current_price = broker.get_current_price(trade.asset)
                if self.close_trade(trade, current_price, reason):
                    closed_count += 1
            except Exception as e:
                self.logger.error(f"Error closing trade {trade_id}: {e}")
        
        return closed_count
    
    def get_active_trades(self) -> List[Trade]:
        """
        Get all active trades.
        
        Returns:
            List of active trades
        """
        return list(self.active_trades.values())
    
    def get_trade_history(
        self,
        asset: Optional[str] = None,
        limit: int = 100
    ) -> List[Trade]:
        """
        Get trade history.
        
        Args:
            asset: Filter by asset (None for all)
            limit: Maximum number to return
            
        Returns:
            List of trades
        """
        history = self.trade_history
        
        if asset:
            history = [t for t in history if t.asset == asset]
        
        return history[-limit:]
    
    def get_trade_statistics(self) -> Dict[str, any]:
        """
        Get trade statistics.
        
        Returns:
            Dictionary with trade statistics
        """
        if not self.trade_history:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'max_drawdown': 0.0
            }
        
        total_trades = len(self.trade_history)
        winning_trades = [t for t in self.trade_history if t.pnl > 0]
        losing_trades = [t for t in self.trade_history if t.pnl < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
        total_pnl = sum(t.pnl for t in self.trade_history)
        
        avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0.0
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0.0
        
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        
        # Calculate max drawdown
        cumulative_pnl = []
        running_total = 0.0
        for trade in self.trade_history:
            running_total += trade.pnl
            cumulative_pnl.append(running_total)
        
        if cumulative_pnl:
            peak = max(cumulative_pnl)
            max_drawdown = min(0, min(cumulative_pnl) - peak)
        else:
            max_drawdown = 0.0
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown
        }
