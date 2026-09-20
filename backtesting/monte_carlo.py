"""
Monte Carlo Simulation for Phoenix Protocol Trading System
Implements Monte Carlo simulation for statistical validation.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass
from copy import deepcopy

from config.strategy_params import BACKTESTING_PARAMS
from backtesting.backtester import BacktestResult, BacktestTrade
from src.utils.logger import get_logger


@dataclass
class MonteCarloResult:
    """Results of Monte Carlo simulation."""
    num_simulations: int
    original_trades: List[BacktestTrade]
    simulated_results: List[Dict[str, float]]
    confidence_intervals: Dict[str, Tuple[float, float]]
    probability_of_profit: float
    probability_of_loss: float
    worst_case_scenario: Dict[str, float]
    best_case_scenario: Dict[str, float]
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary."""
        return {
            'num_simulations': self.num_simulations,
            'original_trades': [t.to_dict() for t in self.original_trades],
            'simulated_results': self.simulated_results,
            'confidence_intervals': self.confidence_intervals,
            'probability_of_profit': self.probability_of_profit,
            'probability_of_loss': self.probability_of_loss,
            'worst_case_scenario': self.worst_case_scenario,
            'best_case_scenario': self.best_case_scenario
        }


class MonteCarloSimulator:
    """
    Monte Carlo simulation for strategy validation.
    Simulates multiple scenarios to assess strategy robustness.
    """
    
    def __init__(self, initial_capital: float = 10000.0):
        """
        Initialize Monte Carlo simulator.
        
        Args:
            initial_capital: Initial capital for simulations
        """
        self.initial_capital = initial_capital
        self.num_simulations = BACKTESTING_PARAMS['monte_carlo_simulations']
        self.logger = get_logger()
    
    def run_simulation(
        self,
        trades: List[BacktestTrade],
        num_simulations: Optional[int] = None
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation on trade results.
        
        Args:
            trades: List of original trades
            num_simulations: Number of simulations (defaults to settings)
            
        Returns:
            MonteCarloResult object
        """
        try:
            self.logger.info(f"Starting Monte Carlo simulation with {len(trades)} trades")
            
            num_simulations = num_simulations or self.num_simulations
            simulated_results = []
            
            # Extract trade PnLs
            trade_pnls = [t.pnl for t in trades]
            
            # Run simulations
            for i in range(num_simulations):
                # Randomize trade order
                shuffled_pnls = np.random.permutation(trade_pnls)
                
                # Calculate cumulative PnL
                cumulative_pnl = np.cumsum(shuffled_pnls)
                final_pnl = cumulative_pnl[-1]
                final_capital = self.initial_capital + final_pnl
                
                # Calculate metrics
                max_drawdown = self._calculate_max_drawdown(cumulative_pnl)
                win_rate = sum(1 for pnl in shuffled_pnls if pnl > 0) / len(shuffled_pnls)
                
                result = {
                    'final_capital': final_capital,
                    'final_pnl': final_pnl,
                    'return_pct': final_pnl / self.initial_capital,
                    'max_drawdown': max_drawdown,
                    'max_drawdown_pct': max_drawdown / self.initial_capital,
                    'win_rate': win_rate,
                    'trades': len(trades)
                }
                
                simulated_results.append(result)
            
            # Calculate statistics
            confidence_intervals = self._calculate_confidence_intervals(simulated_results)
            probability_of_profit = sum(1 for r in simulated_results if r['final_pnl'] > 0) / len(simulated_results)
            probability_of_loss = 1 - probability_of_profit
            
            # Find worst and best cases
            sorted_results = sorted(simulated_results, key=lambda x: x['final_pnl'])
            worst_case = sorted_results[0]
            best_case = sorted_results[-1]
            
            result = MonteCarloResult(
                num_simulations=num_simulations,
                original_trades=trades,
                simulated_results=simulated_results,
                confidence_intervals=confidence_intervals,
                probability_of_profit=probability_of_profit,
                probability_of_loss=probability_of_loss,
                worst_case_scenario=worst_case,
                best_case_scenario=best_case
            )
            
            self.logger.info(f"Monte Carlo simulation completed: {probability_of_profit:.1%} probability of profit")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Monte Carlo simulation error: {e}")
            raise
    
    def _calculate_max_drawdown(self, cumulative_pnl: np.ndarray) -> float:
        """
        Calculate maximum drawdown from cumulative PnL.
        
        Args:
            cumulative_pnl: Array of cumulative PnL values
            
        Returns:
            Maximum drawdown
        """
        peak = np.maximum.accumulate(cumulative_pnl)
        drawdown = cumulative_pnl - peak
        return abs(drawdown.min())
    
    def _calculate_confidence_intervals(
        self,
        results: List[Dict[str, float]],
        confidence_level: float = 0.95
    ) -> Dict[str, Tuple[float, float]]:
        """
        Calculate confidence intervals for metrics.
        
        Args:
            results: List of simulation results
            confidence_level: Confidence level (0.95 = 95%)
            
        Returns:
            Dictionary with confidence intervals
        """
        metrics = ['final_capital', 'final_pnl', 'return_pct', 'max_drawdown', 'win_rate']
        intervals = {}
        
        alpha = 1 - confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100
        
        for metric in metrics:
            values = [r[metric] for r in results]
            lower = np.percentile(values, lower_percentile)
            upper = np.percentile(values, upper_percentile)
            intervals[metric] = (lower, upper)
        
        return intervals
    
    def run_resampling_simulation(
        self,
        trades: List[BacktestTrade],
        sample_size: Optional[int] = None,
        num_simulations: Optional[int] = None
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation with resampling (bootstrap).
        
        Args:
            trades: List of original trades
            sample_size: Size of each sample (defaults to original trade count)
            num_simulations: Number of simulations
            
        Returns:
            MonteCarloResult object
        """
        try:
            self.logger.info("Starting Monte Carlo simulation with resampling")
            
            num_simulations = num_simulations or self.num_simulations
            sample_size = sample_size or len(trades)
            
            simulated_results = []
            trade_pnls = [t.pnl for t in trades]
            
            for i in range(num_simulations):
                # Resample with replacement
                resampled_pnls = np.random.choice(trade_pnls, size=sample_size, replace=True)
                
                # Calculate cumulative PnL
                cumulative_pnl = np.cumsum(resampled_pnls)
                final_pnl = cumulative_pnl[-1]
                final_capital = self.initial_capital + final_pnl
                
                # Calculate metrics
                max_drawdown = self._calculate_max_drawdown(cumulative_pnl)
                win_rate = sum(1 for pnl in resampled_pnls if pnl > 0) / len(resampled_pnls)
                
                result = {
                    'final_capital': final_capital,
                    'final_pnl': final_pnl,
                    'return_pct': final_pnl / self.initial_capital,
                    'max_drawdown': max_drawdown,
                    'max_drawdown_pct': max_drawdown / self.initial_capital,
                    'win_rate': win_rate,
                    'trades': sample_size
                }
                
                simulated_results.append(result)
            
            # Calculate statistics
            confidence_intervals = self._calculate_confidence_intervals(simulated_results)
            probability_of_profit = sum(1 for r in simulated_results if r['final_pnl'] > 0) / len(simulated_results)
            probability_of_loss = 1 - probability_of_profit
            
            # Find worst and best cases
            sorted_results = sorted(simulated_results, key=lambda x: x['final_pnl'])
            worst_case = sorted_results[0]
            best_case = sorted_results[-1]
            
            result = MonteCarloResult(
                num_simulations=num_simulations,
                original_trades=trades,
                simulated_results=simulated_results,
                confidence_intervals=confidence_intervals,
                probability_of_profit=probability_of_profit,
                probability_of_loss=probability_of_loss,
                worst_case_scenario=worst_case,
                best_case_scenario=best_case
            )
            
            self.logger.info(f"Resampling simulation completed: {probability_of_profit:.1%} probability of profit")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Resampling simulation error: {e}")
            raise
    
    def generate_report(self, result: MonteCarloResult) -> str:
        """
        Generate human-readable Monte Carlo report.
        
        Args:
            result: MonteCarloResult object
            
        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 80)
        report.append("MONTE CARLO SIMULATION REPORT")
        report.append("=" * 80)
        report.append("")
        
        report.append(f"Number of Simulations: {result.num_simulations}")
        report.append(f"Original Trades: {len(result.original_trades)}")
        report.append("")
        
        report.append("PROBABILITY ANALYSIS:")
        report.append("-" * 40)
        report.append(f"Probability of Profit: {result.probability_of_profit:.2%}")
        report.append(f"Probability of Loss: {result.probability_of_loss:.2%}")
        report.append("")
        
        report.append("CONFIDENCE INTERVALS (95%):")
        report.append("-" * 40)
        for metric, (lower, upper) in result.confidence_intervals.items():
            report.append(f"{metric}: [{lower:.2f}, {upper:.2f}]")
        report.append("")
        
        report.append("WORST CASE SCENARIO:")
        report.append("-" * 40)
        for key, value in result.worst_case_scenario.items():
            report.append(f"{key}: {value:.4f}")
        report.append("")
        
        report.append("BEST CASE SCENARIO:")
        report.append("-" * 40)
        for key, value in result.best_case_scenario.items():
            report.append(f"{key}: {value:.4f}")
        report.append("")
        
        return "\n".join(report)
