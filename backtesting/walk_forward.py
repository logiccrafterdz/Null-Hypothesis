"""
Walk-Forward Analysis for Null Hypothesis Trading System
Implements walk-forward analysis for robust strategy validation.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from dataclasses import dataclass

from config.strategy_params import BACKTESTING_PARAMS
from backtesting.backtester import Backtester, BacktestResult
from src.utils.logger import get_logger


@dataclass
class WalkForwardSegment:
    """Represents a walk-forward segment."""
    in_sample_start: datetime
    in_sample_end: datetime
    out_of_sample_start: datetime
    out_of_sample_end: datetime
    in_sample_result: BacktestResult
    out_of_sample_result: BacktestResult
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary."""
        return {
            'in_sample_start': self.in_sample_start,
            'in_sample_end': self.in_sample_end,
            'out_of_sample_start': self.out_of_sample_start,
            'out_of_sample_end': self.out_of_sample_end,
            'in_sample_result': self.in_sample_result.to_dict(),
            'out_of_sample_result': self.out_of_sample_result.to_dict()
        }


@dataclass
class WalkForwardResult:
    """Results of walk-forward analysis."""
    segments: List[WalkForwardSegment]
    aggregate_in_sample: Dict[str, float]
    aggregate_out_of_sample: Dict[str, float]
    robustness_score: float
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary."""
        return {
            'segments': [s.to_dict() for s in self.segments],
            'aggregate_in_sample': self.aggregate_in_sample,
            'aggregate_out_of_sample': self.aggregate_out_of_sample,
            'robustness_score': self.robustness_score
        }


class WalkForwardAnalyzer:
    """
    Walk-forward analysis for strategy validation.
    Tests strategy on multiple in-sample/out-of-sample periods.
    """
    
    def __init__(self, backtester: Backtester):
        """
        Initialize walk-forward analyzer.
        
        Args:
            backtester: Backtester instance
        """
        self.backtester = backtester
        self.logger = get_logger()
        
        self.window_size_months = BACKTESTING_PARAMS['walk_forward_window']
        self.step_size_months = BACKTESTING_PARAMS['walk_forward_step']
    
    def run_walk_forward(
        self,
        data: pd.DataFrame,
        asset: str,
        start_date: datetime,
        end_date: datetime
    ) -> WalkForwardResult:
        """
        Run walk-forward analysis.
        
        Args:
            data: DataFrame with OHLCV data
            asset: Asset symbol
            start_date: Overall start date
            end_date: Overall end date
            
        Returns:
            WalkForwardResult object
        """
        try:
            self.logger.info(f"Starting walk-forward analysis for {asset}")
            
            segments = []
            
            # Calculate segment dates
            window_size = timedelta(days=self.window_size_months * 30)
            step_size = timedelta(days=self.step_size_months * 30)
            
            current_start = start_date
            
            while current_start + window_size < end_date:
                in_sample_end = current_start + window_size
                out_of_sample_start = in_sample_end
                out_of_sample_end = min(out_of_sample_start + step_size, end_date)
                
                if out_of_sample_end <= out_of_sample_start:
                    break
                
                self.logger.info(f"Processing segment: {current_start} to {out_of_sample_end}")
                
                # Run in-sample backtest
                in_sample_result = self.backtester.run_backtest(
                    data,
                    asset,
                    current_start,
                    in_sample_end
                )
                
                # Run out-of-sample backtest
                out_of_sample_result = self.backtester.run_backtest(
                    data,
                    asset,
                    out_of_sample_start,
                    out_of_sample_end
                )
                
                segment = WalkForwardSegment(
                    in_sample_start=current_start,
                    in_sample_end=in_sample_end,
                    out_of_sample_start=out_of_sample_start,
                    out_of_sample_end=out_of_sample_end,
                    in_sample_result=in_sample_result,
                    out_of_sample_result=out_of_sample_result
                )
                
                segments.append(segment)
                
                # Move to next segment
                current_start += step_size
            
            # Calculate aggregate results
            aggregate_in_sample = self._calculate_aggregate_results(
                [s.in_sample_result for s in segments]
            )
            aggregate_out_of_sample = self._calculate_aggregate_results(
                [s.out_of_sample_result for s in segments]
            )
            
            # Calculate robustness score
            robustness_score = self._calculate_robustness_score(
                aggregate_in_sample,
                aggregate_out_of_sample
            )
            
            result = WalkForwardResult(
                segments=segments,
                aggregate_in_sample=aggregate_in_sample,
                aggregate_out_of_sample=aggregate_out_of_sample,
                robustness_score=robustness_score
            )
            
            self.logger.info(f"Walk-forward analysis completed: {len(segments)} segments")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Walk-forward analysis error: {e}")
            raise
    
    def _calculate_aggregate_results(
        self,
        results: List[BacktestResult]
    ) -> Dict[str, float]:
        """
        Calculate aggregate results from multiple backtests.
        
        Args:
            results: List of BacktestResult objects
            
        Returns:
            Dictionary with aggregate metrics
        """
        if not results:
            return {}
        
        valid_results = [r for r in results if r.status.value == 'completed']
        
        if not valid_results:
            return {}
        
        total_trades = sum(r.total_trades for r in valid_results)
        total_return = sum(r.total_return for r in valid_results)
        
        winning_trades = sum(r.winning_trades for r in valid_results)
        losing_trades = sum(r.losing_trades for r in valid_results)
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        gross_profit = sum(r.avg_win * r.winning_trades for r in valid_results)
        gross_loss = sum(abs(r.avg_loss) * r.losing_trades for r in valid_results)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        
        avg_return = total_return / len(valid_results)
        avg_return_pct = avg_return / self.backtester.initial_capital
        
        # Calculate average max drawdown
        avg_max_drawdown_pct = np.mean([r.max_drawdown_pct for r in valid_results])
        
        # Calculate average Sharpe ratio
        avg_sharpe_ratio = np.mean([r.sharpe_ratio for r in valid_results])
        
        return {
            'total_trades': total_trades,
            'total_return': total_return,
            'total_return_pct': total_return / self.backtester.initial_capital,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_max_drawdown_pct': avg_max_drawdown_pct,
            'avg_sharpe_ratio': avg_sharpe_ratio,
            'segments_tested': len(valid_results)
        }
    
    def _calculate_robustness_score(
        self,
        in_sample: Dict[str, float],
        out_of_sample: Dict[str, float]
    ) -> float:
        """
        Calculate robustness score based on in-sample vs out-of-sample performance.
        
        Args:
            in_sample: In-sample aggregate results
            out_of_sample: Out-of-sample aggregate results
            
        Returns:
            Robustness score (0.0 to 1.0)
        """
        if not in_sample or not out_of_sample:
            return 0.0
        
        score = 0.0
        
        # Win rate degradation (should be minimal)
        in_win_rate = in_sample.get('win_rate', 0.0)
        out_win_rate = out_of_sample.get('win_rate', 0.0)
        win_rate_ratio = out_win_rate / in_win_rate if in_win_rate > 0 else 0.0
        score += min(win_rate_ratio, 1.0) * 0.3
        
        # Profit factor degradation
        in_pf = in_sample.get('profit_factor', 0.0)
        out_pf = out_of_sample.get('profit_factor', 0.0)
        pf_ratio = out_pf / in_pf if in_pf > 0 else 0.0
        score += min(pf_ratio, 1.0) * 0.3
        
        # Return consistency
        in_return = in_sample.get('total_return_pct', 0.0)
        out_return = out_of_sample.get('total_return_pct', 0.0)
        return_ratio = out_return / in_return if in_return > 0 else 0.0
        score += min(return_ratio, 1.0) * 0.2
        
        # Drawdown control
        out_drawdown = abs(out_of_sample.get('avg_max_drawdown_pct', 0.0))
        drawdown_score = max(0, 1 - out_drawdown * 2)  # Penalize high drawdown
        score += drawdown_score * 0.2
        
        return min(score, 1.0)
    
    def generate_report(self, result: WalkForwardResult) -> str:
        """
        Generate human-readable walk-forward report.
        
        Args:
            result: WalkForwardResult object
            
        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 80)
        report.append("WALK-FORWARD ANALYSIS REPORT")
        report.append("=" * 80)
        report.append("")
        
        report.append(f"Segments Tested: {len(result.segments)}")
        report.append(f"Robustness Score: {result.robustness_score:.2f}")
        report.append("")
        
        report.append("IN-SAMPLE AGGREGATE RESULTS:")
        report.append("-" * 40)
        for key, value in result.aggregate_in_sample.items():
            report.append(f"{key}: {value:.4f}")
        report.append("")
        
        report.append("OUT-OF-SAMPLE AGGREGATE RESULTS:")
        report.append("-" * 40)
        for key, value in result.aggregate_out_of_sample.items():
            report.append(f"{key}: {value:.4f}")
        report.append("")
        
        report.append("SEGMENT DETAILS:")
        report.append("-" * 40)
        for i, segment in enumerate(result.segments, 1):
            report.append(f"Segment {i}:")
            report.append(f"  In-Sample: {segment.in_sample_start} to {segment.in_sample_end}")
            report.append(f"  Return: {segment.in_sample_result.total_return_pct:.2%}")
            report.append(f"  Win Rate: {segment.in_sample_result.win_rate:.2%}")
            report.append(f"  Out-of-Sample: {segment.out_of_sample_start} to {segment.out_of_sample_end}")
            report.append(f"  Return: {segment.out_of_sample_result.total_return_pct:.2%}")
            report.append(f"  Win Rate: {segment.out_of_sample_result.win_rate:.2%}")
            report.append("")
        
        return "\n".join(report)
