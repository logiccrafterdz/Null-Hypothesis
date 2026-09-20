"""
Backtesting Engine for Phoenix Protocol Trading System
Comprehensive backtesting with realistic trade simulation.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pytz

from config.settings import BACKTESTING_INITIAL_CAPITAL, BACKTESTING_COMMISSION, BACKTESTING_SPREAD, BACKTESTING_SLIPPAGE
from config.strategy_params import (
    TRADE_MANAGEMENT,
    RISK_MANAGEMENT,
    BACKTESTING_PARAMS,
    SUCCESS_CRITERIA
)
from src.utils.logger import get_logger
from src.utils.indicators import calculate_atr


class BacktestStatus(Enum):
    """Backtest status types."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class BacktestTrade:
    """Represents a trade in backtesting."""
    entry_time: datetime
    exit_time: datetime
    asset: str
    direction: str
    entry_price: float
    exit_price: float
    size: float
    stop_loss: float
    take_profit: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    max_profit: float = 0.0
    max_loss: float = 0.0
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary."""
        return {
            'entry_time': self.entry_time,
            'exit_time': self.exit_time,
            'asset': self.asset,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'size': self.size,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            'exit_reason': self.exit_reason,
            'max_profit': self.max_profit,
            'max_loss': self.max_loss
        }


@dataclass
class BacktestResult:
    """Results of a backtest."""
    status: BacktestStatus
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    avg_win: float
    avg_loss: float
    avg_trade: float
    trades: List[BacktestTrade]
    equity_curve: pd.Series
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary."""
        return {
            'status': self.status.value,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.initial_capital,
            'final_capital': self.final_capital,
            'total_return': self.total_return,
            'total_return_pct': self.total_return_pct,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': self.max_drawdown_pct,
            'sharpe_ratio': self.sharpe_ratio,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'avg_trade': self.avg_trade,
            'trades': [t.to_dict() for t in self.trades],
            'error_message': self.error_message
        }


class Backtester:
    """
    Comprehensive backtesting engine.
    Simulates trading with realistic costs and slippage.
    """
    
    def __init__(self, initial_capital: Optional[float] = None):
        """
        Initialize backtester.
        
        Args:
            initial_capital: Initial capital (defaults to settings)
        """
        self.initial_capital = initial_capital or BACKTESTING_INITIAL_CAPITAL
        self.commission = BACKTESTING_COMMISSION
        self.spread = BACKTESTING_SPREAD
        self.slippage = BACKTESTING_SLIPPAGE
        
        self.logger = get_logger()
        
        # Strategy parameters
        self.stop_loss_pct = TRADE_MANAGEMENT['stop_loss_pct']
        self.take_profit_pct = TRADE_MANAGEMENT['take_profit_pct']
        self.position_size_risk = TRADE_MANAGEMENT['position_size_risk']
        self.max_open_trades = RISK_MANAGEMENT['max_open_trades']
    
    def run_backtest(
        self,
        data: pd.DataFrame,
        asset: str,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResult:
        """
        Run backtest on historical data.
        
        Args:
            data: DataFrame with OHLCV data
            asset: Asset symbol
            start_date: Start date
            end_date: End date
            
        Returns:
            BacktestResult object
        """
        try:
            self.logger.info(f"Starting backtest for {asset} from {start_date} to {end_date}")
            
            # Filter data by date range
            data = data[(data.index >= start_date) & (data.index <= end_date)].copy()
            
            if len(data) < 100:
                return self._create_error_result("Insufficient data for backtesting")
            
            # Initialize
            capital = self.initial_capital
            equity_curve = []
            trades = []
            open_positions = []
            
            # Run simulation
            for i in range(len(data)):
                current_time = data.index[i]
                row = data.iloc[i]
                
                # Check for bad luck moment
                signal = self._check_signal(data.iloc[:i+1], asset, current_time)
                
                if signal and len(open_positions) < self.max_open_trades:
                    # Execute trade
                    trade = self._execute_trade(
                        signal,
                        row,
                        capital,
                        asset,
                        current_time
                    )
                    
                    if trade:
                        open_positions.append(trade)
                        capital -= trade.size * trade.entry_price * self.commission
                
                # Monitor open positions
                open_positions = self._monitor_positions(
                    open_positions,
                    row,
                    current_time
                )
                
                # Update equity
                open_pnl = sum(p['current_pnl'] for p in open_positions)
                current_equity = capital + open_pnl
                equity_curve.append(current_equity)
            
            # Close remaining positions
            for position in open_positions:
                exit_price = data['close'].iloc[-1]
                trade = self._close_position(
                    position,
                    exit_price,
                    end_date,
                    "End of Backtest"
                )
                if trade:
                    trades.append(trade)
                    capital += trade.pnl
            
            # Calculate results
            result = self._calculate_results(
                capital,
                trades,
                equity_curve,
                start_date,
                end_date,
                asset
            )
            
            self.logger.info(f"Backtest completed: {result.total_trades} trades, {result.total_return_pct:.2%} return")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Backtest error: {e}")
            return self._create_error_result(str(e))
    
    def _check_signal(
        self,
        data: pd.DataFrame,
        asset: str,
        current_time: datetime
    ) -> Optional[Dict[str, any]]:
        """
        Check for trading signal (simplified bad luck moment detection).
        
        Args:
            data: Historical data
            asset: Asset symbol
            current_time: Current time
            
        Returns:
            Signal dictionary or None
        """
        if len(data) < 20:
            return None
        
        # Simplified bad luck moment detection
        current_close = data['close'].iloc[-1]
        previous_close = data['close'].iloc[-2]
        current_volume = data['volume'].iloc[-1]
        avg_volume = data['volume'].iloc[-20:-1].mean()
        
        # Price drop
        drop_pct = (previous_close - current_close) / previous_close
        if drop_pct < 0.02:  # Less than 2% drop
            return None
        
        # Volume spike
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        if volume_ratio < 1.5:  # Less than 1.5x volume
            return None
        
        # Volatility check
        atr = calculate_atr(data, 14)
        if len(atr) < 2:
            return None
        
        current_atr = atr.iloc[-1]
        avg_atr = atr.iloc[-20:-1].mean()
        if avg_atr > 0 and current_atr / avg_atr < 1.3:
            return None
        
        # Random decision (simplified)
        import random
        if random.random() > 0.6:  # 60% entry probability
            return None
        
        return {
            'direction': 'LONG',
            'entry_price': current_close,
            'confidence': 1.0
        }
    
    def _execute_trade(
        self,
        signal: Dict[str, any],
        row: pd.Series,
        capital: float,
        asset: str,
        current_time: datetime
    ) -> Dict[str, any]:
        """
        Execute a trade in backtesting.
        
        Args:
            signal: Trading signal
            row: Current data row
            capital: Available capital
            asset: Asset symbol
            current_time: Current time
            
        Returns:
            Position dictionary
        """
        direction = signal['direction']
        entry_price = signal['entry_price']
        
        # Apply slippage
        if direction == 'LONG':
            entry_price = entry_price * (1 + self.slippage)
        else:
            entry_price = entry_price * (1 - self.slippage)
        
        # Calculate position size
        stop_loss_price = entry_price * (1 - self.stop_loss_pct) if direction == 'LONG' else entry_price * (1 + self.stop_loss_pct)
        risk_amount = capital * self.position_size_risk
        stop_loss_amount = abs(entry_price - stop_loss_price)
        position_size = risk_amount / stop_loss_amount if stop_loss_amount > 0 else 0
        
        # Calculate take profit
        take_profit_price = entry_price * (1 + self.take_profit_pct) if direction == 'LONG' else entry_price * (1 - self.take_profit_pct)
        
        return {
            'entry_time': current_time,
            'asset': asset,
            'direction': direction,
            'entry_price': entry_price,
            'size': position_size,
            'stop_loss': stop_loss_price,
            'take_profit': take_profit_price,
            'current_pnl': 0.0,
            'max_profit': 0.0,
            'max_loss': 0.0
        }
    
    def _monitor_positions(
        self,
        open_positions: List[Dict],
        row: pd.Series,
        current_time: datetime
    ) -> List[Dict]:
        """
        Monitor and update open positions.
        
        Args:
            open_positions: List of open positions
            row: Current data row
            current_time: Current time
            
        Returns:
            Updated list of open positions
        """
        current_price = row['close']
        remaining_positions = []
        
        for position in open_positions:
            direction = position['direction']
            entry_price = position['entry_price']
            stop_loss = position['stop_loss']
            take_profit = position['take_profit']
            
            # Calculate current PnL
            if direction == 'LONG':
                pnl_pct = (current_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - current_price) / entry_price
            
            position['current_pnl'] = position['size'] * (current_price - entry_price) if direction == 'LONG' else position['size'] * (entry_price - current_price)
            
            # Update max profit/loss
            if pnl_pct > position['max_profit']:
                position['max_profit'] = pnl_pct
            if pnl_pct < position['max_loss']:
                position['max_loss'] = pnl_pct
            
            # Check exit conditions
            should_close = False
            exit_reason = ""
            
            if direction == 'LONG':
                if current_price <= stop_loss:
                    should_close = True
                    exit_reason = "Stop Loss"
                elif current_price >= take_profit:
                    should_close = True
                    exit_reason = "Take Profit"
            else:
                if current_price >= stop_loss:
                    should_close = True
                    exit_reason = "Stop Loss"
                elif current_price <= take_profit:
                    should_close = True
                    exit_reason = "Take Profit"
            
            if should_close:
                # Trade will be closed in next iteration
                remaining_positions.append(position)
            else:
                remaining_positions.append(position)
        
        return remaining_positions
    
    def _close_position(
        self,
        position: Dict,
        exit_price: float,
        exit_time: datetime,
        exit_reason: str
    ) -> Optional[BacktestTrade]:
        """
        Close a position.
        
        Args:
            position: Position dictionary
            exit_price: Exit price
            exit_time: Exit time
            exit_reason: Reason for closing
            
        Returns:
            BacktestTrade object
        """
        direction = position['direction']
        entry_price = position['entry_price']
        size = position['size']
        
        # Apply slippage to exit
        if direction == 'LONG':
            exit_price = exit_price * (1 - self.slippage)
        else:
            exit_price = exit_price * (1 + self.slippage)
        
        # Calculate PnL
        if direction == 'LONG':
            pnl = size * (exit_price - entry_price)
        else:
            pnl = size * (entry_price - exit_price)
        
        # Subtract commission
        pnl -= size * exit_price * self.commission
        
        pnl_pct = pnl / (entry_price * size)
        
        return BacktestTrade(
            entry_time=position['entry_time'],
            exit_time=exit_time,
            asset=position['asset'],
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            size=size,
            stop_loss=position['stop_loss'],
            take_profit=position['take_profit'],
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=exit_reason,
            max_profit=position['max_profit'],
            max_loss=position['max_loss']
        )
    
    def _calculate_results(
        self,
        final_capital: float,
        trades: List[BacktestTrade],
        equity_curve: List[float],
        start_date: datetime,
        end_date: datetime,
        asset: str
    ) -> BacktestResult:
        """
        Calculate backtest results.
        
        Args:
            final_capital: Final capital
            trades: List of trades
            equity_curve: Equity curve data
            start_date: Start date
            end_date: End date
            asset: Asset symbol
            
        Returns:
            BacktestResult object
        """
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
        
        total_return = final_capital - self.initial_capital
        total_return_pct = total_return / self.initial_capital
        
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        
        avg_win = gross_profit / len(winning_trades) if winning_trades else 0.0
        avg_loss = gross_loss / len(losing_trades) if losing_trades else 0.0
        avg_trade = total_return / total_trades if total_trades > 0 else 0.0
        
        # Calculate max drawdown
        equity_series = pd.Series(equity_curve)
        if len(equity_series) > 0:
            peak = equity_series.expanding().max()
            drawdown = (equity_series - peak) / peak
            max_drawdown_pct = drawdown.min()
            max_drawdown = abs(max_drawdown_pct * self.initial_capital)
        else:
            max_drawdown_pct = 0.0
            max_drawdown = 0.0
        
        # Calculate Sharpe ratio (simplified)
        if len(equity_curve) > 1:
            returns = pd.Series(equity_curve).pct_change().dropna()
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0.0
        else:
            sharpe_ratio = 0.0
        
        return BacktestResult(
            status=BacktestStatus.COMPLETED,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_trade=avg_trade,
            trades=trades,
            equity_curve=pd.Series(equity_curve)
        )
    
    def _create_error_result(self, error_message: str) -> BacktestResult:
        """Create error result."""
        return BacktestResult(
            status=BacktestStatus.ERROR,
            start_date=datetime.now(),
            end_date=datetime.now(),
            initial_capital=self.initial_capital,
            final_capital=self.initial_capital,
            total_return=0.0,
            total_return_pct=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            avg_trade=0.0,
            trades=[],
            equity_curve=pd.Series(),
            error_message=error_message
        )
    
    def check_success_criteria(self, result: BacktestResult) -> Dict[str, bool]:
        """
        Check if backtest meets success criteria.
        
        Args:
            result: BacktestResult object
            
        Returns:
            Dictionary with criteria check results
        """
        return {
            'min_win_rate': result.win_rate >= SUCCESS_CRITERIA['min_win_rate'],
            'min_profit_factor': result.profit_factor >= SUCCESS_CRITERIA['min_profit_factor'],
            'max_drawdown': abs(result.max_drawdown_pct) <= SUCCESS_CRITERIA['max_drawdown'],
            'min_sharpe_ratio': result.sharpe_ratio >= SUCCESS_CRITERIA['min_sharpe_ratio'],
            'min_trades': result.total_trades >= SUCCESS_CRITERIA['min_trades'],
            'overall': all([
                result.win_rate >= SUCCESS_CRITERIA['min_win_rate'],
                result.profit_factor >= SUCCESS_CRITERIA['min_profit_factor'],
                abs(result.max_drawdown_pct) <= SUCCESS_CRITERIA['max_drawdown'],
                result.sharpe_ratio >= SUCCESS_CRITERIA['min_sharpe_ratio'],
                result.total_trades >= SUCCESS_CRITERIA['min_trades']
            ])
        }
