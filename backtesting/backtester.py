"""
Backtesting Engine for Null Hypothesis Trading System
Comprehensive backtesting with realistic trade simulation.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from config.settings import BACKTESTING_INITIAL_CAPITAL, BACKTESTING_COMMISSION, BACKTESTING_SPREAD, BACKTESTING_SLIPPAGE
from config.strategy_params import (
    TRADE_MANAGEMENT,
    RISK_MANAGEMENT,
    BAD_LUCK_DETECTOR,
    SYMBOL_METADATA,
    SUCCESS_CRITERIA
)
from src.utils.logger import get_logger
from src.utils.helpers import calculate_position_size
from src.core.market_analyzer import MarketAnalyzer
from src.core.decision_engine import DecisionEngine


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
    
    def __init__(
        self,
        initial_capital: Optional[float] = None,
        market_analyzer: Optional[MarketAnalyzer] = None,
        decision_engine: Optional[DecisionEngine] = None
    ):
        """
        Initialize backtester.
        
        Args:
            initial_capital: Initial capital (defaults to settings)
            market_analyzer: Market analyzer (defaults to production instance)
            decision_engine: Decision engine (defaults to production instance)
        """
        self.initial_capital = initial_capital or BACKTESTING_INITIAL_CAPITAL
        self.commission = BACKTESTING_COMMISSION
        self.spread = BACKTESTING_SPREAD
        self.slippage = BACKTESTING_SLIPPAGE
        
        self.logger = get_logger()
        
        # Production detection pipeline (same as live trading)
        self.analyzer = market_analyzer or MarketAnalyzer()
        self.decision_engine = decision_engine or DecisionEngine()
        
        # Strategy parameters
        self.stop_loss_pct = TRADE_MANAGEMENT['stop_loss_pct']
        self.take_profit_pct = TRADE_MANAGEMENT['take_profit_pct']
        self.position_size_risk = TRADE_MANAGEMENT['position_size_risk']
        self.max_open_trades = RISK_MANAGEMENT['max_open_trades']
        self.trailing_stop = TRADE_MANAGEMENT['trailing_stop']
        self.trailing_activation_pct = TRADE_MANAGEMENT['trailing_activation_pct']
        self.trailing_distance_pct = TRADE_MANAGEMENT['trailing_distance_pct']
        self.max_duration_candles = TRADE_MANAGEMENT['max_duration_candles']
        
        # Diagnostic counters (reset per run_backtest call, not part of
        # result calculation; used by reporting tooling). They describe the
        # signal -> entry funnel: detector fires (_signal_count), passed the
        # randomness engine (_random_refusal_count skipped), risk-gate
        # blocking (max open / cooldown / daily / weekly loss), and minimum
        # lot sizing refusals (_size_refusal_count).
        self._signal_count = 0
        self._entry_count = 0
        self._size_refusal_count = 0
        self._random_refusal_count = 0
        self._max_open_refusal_count = 0
        self._cooldown_refusal_count = 0
        self._daily_loss_refusal_count = 0
        self._weekly_loss_refusal_count = 0

        # Optional risk-limit simulation (off by default so historical runs
        # keep their existing semantics; enabled per-call for the real-data
        # validation report). Mirrors RiskManager: max_daily_loss (5%),
        # max_weekly_loss (10%), cooldown_after_loss trades, max_open_trades.
        self.enforce_risk_limits = False
        self._risk_daily_pnl = 0.0
        self._risk_daily_date = None
        self._risk_weekly_pnl = 0.0
        self._risk_week_start = None
        self._risk_cooldown_remaining = 0

        # Vectorized pre-filter for the per-bar detector (see
        # MarketAnalyzer.precompute_verdict_mask). None disables the fast
        # path so _check_signal always runs the production detector.
        self._verdict_mask = None
    
    def run_backtest(
        self,
        data: pd.DataFrame,
        asset: str,
        start_date: datetime,
        end_date: datetime,
        enforce_risk_limits: bool = False
    ) -> BacktestResult:
        """
        Run backtest on historical data.
        
        Args:
            data: DataFrame with OHLCV data
            asset: Asset symbol
            start_date: Start date
            end_date: End date
            enforce_risk_limits: When True, mirror the live RiskManager rules
                (daily/weekly loss caps, cooldown after losses, max open
                positions) during simulation. Default False preserves the
                existing pipeline semantics.
            
        Returns:
            BacktestResult object
        """
        try:
            self.logger.info(f"Starting backtest for {asset} from {start_date} to {end_date}")
            
            # Filter data by date range
            data = data[(data.index >= start_date) & (data.index <= end_date)].copy()
            
            if len(data) < BAD_LUCK_DETECTOR['warmup_bars']:
                return self._create_error_result("Insufficient data for backtesting")
            
            # Reset diagnostic counters for this run
            self._signal_count = 0
            self._entry_count = 0
            self._size_refusal_count = 0
            self._random_refusal_count = 0
            self._max_open_refusal_count = 0
            self._cooldown_refusal_count = 0
            self._daily_loss_refusal_count = 0
            self._weekly_loss_refusal_count = 0
            self.enforce_risk_limits = enforce_risk_limits
            self._risk_daily_pnl = 0.0
            self._risk_daily_date = None
            self._risk_weekly_pnl = 0.0
            self._risk_week_start = data.index.min().normalize() - pd.Timedelta(
                days=data.index.min().weekday()
            )
            self._risk_cooldown_remaining = 0
            self._verdict_mask = self.analyzer.precompute_verdict_mask(data, asset)
            
            # Initialize
            capital = self.initial_capital
            equity_curve = []
            trades = []
            open_positions = []
            
            # Run simulation
            for i in range(len(data)):
                current_time = data.index[i]
                row = data.iloc[i]
                
                # Monitor open positions (opened on previous bars)
                open_positions, closed_trades = self._monitor_positions(
                    open_positions,
                    row,
                    current_time
                )
                
                # Settle closed trades
                for closed_trade in closed_trades:
                    trades.append(closed_trade)
                    capital += closed_trade.pnl
                    if self.enforce_risk_limits:
                        # Mirror RiskManager.record_trade_pnl using the
                        # simulated clock (day/week rollovers handled by
                        # _risk_roll_windows on the next bar).
                        self._risk_daily_pnl += closed_trade.pnl
                        self._risk_weekly_pnl += closed_trade.pnl
                        if closed_trade.pnl < 0:
                            self._risk_cooldown_remaining = RISK_MANAGEMENT['cooldown_after_loss']
                        else:
                            self._risk_cooldown_remaining = 0
                
                # Check for bad luck moment on a bounded window (the detector only
                # needs ~40 bars of context; slicing the growing frame every
                # bar turned the simulation O(n^2) on long histories).
                window = data.iloc[max(0, i - 63):i + 1]
                signal = self._check_signal(window, asset, current_time)

                if signal and self.enforce_risk_limits:
                    # Mirror RiskManager.can_open_trade gate ordering:
                    # daily loss -> weekly loss -> max positions -> cooldown.
                    self._risk_roll_windows(current_time)
                    daily_limit = capital * RISK_MANAGEMENT['max_daily_loss']
                    if self._risk_daily_pnl < -daily_limit:
                        self._daily_loss_refusal_count += 1
                        signal = None
                    else:
                        weekly_limit = capital * RISK_MANAGEMENT['max_weekly_loss']
                        if self._risk_weekly_pnl < -weekly_limit:
                            self._weekly_loss_refusal_count += 1
                            signal = None

                if signal and len(open_positions) >= self.max_open_trades:
                    self._max_open_refusal_count += 1
                    signal = None

                if signal and self.enforce_risk_limits and self._risk_cooldown_remaining > 0:
                    # Each blocked opportunity depletes the cooldown (same
                    # behaviour as RiskManager.update_cooldown).
                    self._cooldown_refusal_count += 1
                    self._risk_cooldown_remaining -= 1
                    signal = None

                if signal:
                    # Execute trade
                    position = self._execute_trade(
                        signal,
                        row,
                        capital,
                        asset,
                        current_time
                    )
                    
                    if position:
                        open_positions.append(position)
                        self._entry_count += 1
                        capital -= position['size'] * position['contract_size'] * position['entry_price'] * self.commission
                
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
    
    def _risk_roll_windows(self, current_time: datetime) -> None:
        """Roll the simulated daily/weekly loss windows (mirrors
        RiskManager._check_reset_periods but keyed to the simulated clock)."""
        today = current_time.date()
        week_start = current_time.normalize() - pd.Timedelta(days=current_time.weekday())
        if self._risk_daily_date is None:
            self._risk_daily_date = today
        elif today > self._risk_daily_date:
            self._risk_daily_pnl = 0.0
            self._risk_daily_date = today
        if week_start > self._risk_week_start:
            self._risk_weekly_pnl = 0.0
            self._risk_week_start = week_start

    def _check_signal(
        self,
        data: pd.DataFrame,
        asset: str,
        current_time: datetime
    ) -> Optional[Dict[str, any]]:
        """
        Check for trading signal using the production bad luck moment detector.

        Uses the exact same MarketAnalyzer + DecisionEngine pipeline as live
        trading so the backtest reflects production thresholds (drop 3%,
        volume 2x, ATR 1.5x and reversal patterns).

        Args:
            data: Historical data
            asset: Asset symbol
            current_time: Current time

        Returns:
            Signal dictionary or None
        """
        if len(data) < 20:
            return None

        # Fast path: skip the full detector when the vectorized gate proves
        # detect_bad_luck_moment could not fire on this bar. The mask is
        # exact (position-invariant indicators) and _check_signal remains the
        # authoritative oracle, so this never changes results.
        mask = getattr(self, '_verdict_mask', None)
        if mask is not None:
            if not mask.loc[data.index[-1]]:
                return None

        # Production detection pipeline
        moment = self.analyzer.detect_bad_luck_moment(data, asset, current_time)
        if moment is None:
            return None
        self._signal_count += 1

        # Organized randomness decision (same engine as live trading)
        should_enter, _ = self.decision_engine.decide_on_bad_luck_moment(moment)
        if not should_enter:
            self._random_refusal_count += 1
            return None

        return {
            'direction': 'LONG',
            'entry_price': data['close'].iloc[-1],
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
        
        # Calculate position size in MT5 lots using the exact same production
        # sizing as live trading (contract size, lot step, min/max lot).
        size = calculate_position_size(
            capital,
            self.position_size_risk,
            self.stop_loss_pct,
            entry_price,
            asset
        )
        if size <= 0:
            # Risk budget cannot cover a minimum lot: refuse the trade.
            self._size_refusal_count += 1
            return None
        
        stop_loss_price = entry_price * (1 - self.stop_loss_pct) if direction == 'LONG' else entry_price * (1 + self.stop_loss_pct)
        contract_size = SYMBOL_METADATA[asset]['contract_size']
        
        # Calculate take profit
        take_profit_price = entry_price * (1 + self.take_profit_pct) if direction == 'LONG' else entry_price * (1 - self.take_profit_pct)
        
        return {
            'entry_time': current_time,
            'asset': asset,
            'direction': direction,
            'entry_price': entry_price,
            'size': size,
            'contract_size': contract_size,
            'stop_loss': stop_loss_price,
            'take_profit': take_profit_price,
            'current_pnl': 0.0,
            'max_profit': 0.0,
            'max_loss': 0.0,
            'bars_held': 0,
            'trailing_active': False
        }
    
    def _monitor_positions(
        self,
        open_positions: List[Dict],
        row: pd.Series,
        current_time: datetime
    ) -> Tuple[List[Dict], List[BacktestTrade]]:
        """
        Monitor and update open positions, closing them on exit conditions.

        Args:
            open_positions: List of open positions
            row: Current data row
            current_time: Current time

        Returns:
            Tuple of (remaining_positions, closed_trades)
        """
        current_price = row['close']
        bar_high = row['high']
        bar_low = row['low']
        remaining_positions = []
        closed_positions = []

        for position in open_positions:
            direction = position['direction']
            entry_price = position['entry_price']
            stop_loss = position['stop_loss']
            take_profit = position['take_profit']

            # Track how many bars the position has been held
            bars_held = position.get('bars_held', 0) + 1
            position['bars_held'] = bars_held

            # Calculate current PnL
            current_pnl = position['size'] * position['contract_size'] * (current_price - entry_price) if direction == 'LONG' else position['size'] * position['contract_size'] * (entry_price - current_price)
            position['current_pnl'] = current_pnl

            pnl_pct = (current_price - entry_price) / entry_price if direction == 'LONG' else (entry_price - current_price) / entry_price

            # Update max profit/loss
            if pnl_pct > position['max_profit']:
                position['max_profit'] = pnl_pct
            if pnl_pct < position['max_loss']:
                position['max_loss'] = pnl_pct

            # Trailing stop logic
            trailing_active = position.get('trailing_active', False)
            if self.trailing_stop and pnl_pct >= self.trailing_activation_pct:
                if direction == 'LONG':
                    new_stop = current_price * (1 - self.trailing_distance_pct)
                    if new_stop > stop_loss:
                        stop_loss = new_stop
                        position['stop_loss'] = new_stop
                        trailing_active = True
                        position['trailing_active'] = True
                else:
                    new_stop = current_price * (1 + self.trailing_distance_pct)
                    if new_stop < stop_loss:
                        stop_loss = new_stop
                        position['stop_loss'] = new_stop
                        trailing_active = True
                        position['trailing_active'] = True

            # Check exit conditions using the bar's full range
            should_close = False
            exit_reason = ""
            exit_price = current_price

            if direction == 'LONG':
                if stop_loss is not None and bar_low <= stop_loss:
                    should_close = True
                    exit_reason = "Trailing Stop" if trailing_active else "Stop Loss"
                    exit_price = stop_loss
                elif take_profit is not None and bar_high >= take_profit:
                    should_close = True
                    exit_reason = "Take Profit"
                    exit_price = take_profit
            else:
                if stop_loss is not None and bar_high >= stop_loss:
                    should_close = True
                    exit_reason = "Trailing Stop" if trailing_active else "Stop Loss"
                    exit_price = stop_loss
                elif take_profit is not None and bar_low <= take_profit:
                    should_close = True
                    exit_reason = "Take Profit"
                    exit_price = take_profit

            # Max duration check
            if not should_close and bars_held >= self.max_duration_candles:
                should_close = True
                exit_reason = "MAX_DURATION_REACHED"
                exit_price = current_price

            if should_close:
                closed_trade = self._close_position(
                    position,
                    exit_price,
                    current_time,
                    exit_reason
                )
                if closed_trade:
                    closed_positions.append(closed_trade)
            else:
                remaining_positions.append(position)

        return remaining_positions, closed_positions
    
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
        contract_size = position['contract_size']
        notional = size * contract_size
        
        # Apply slippage to exit
        if direction == 'LONG':
            exit_price = exit_price * (1 - self.slippage)
        else:
            exit_price = exit_price * (1 + self.slippage)
        
        # Calculate PnL (size is an MT5 lot volume)
        if direction == 'LONG':
            pnl = notional * (exit_price - entry_price)
        else:
            pnl = notional * (entry_price - exit_price)
        
        # Subtract commission
        pnl -= notional * exit_price * self.commission
        
        pnl_pct = pnl / (entry_price * notional)
        
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
        # Zero losing trades means profit factor is unbounded, not 0.
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = float('inf')
        else:
            profit_factor = 0.0
        
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
