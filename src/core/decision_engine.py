"""
Random Decision Engine for Phoenix Protocol Trading System
Implements organized randomness in entry decisions to avoid prediction.
"""

import secrets
import random
from typing import Optional
from datetime import datetime
import pytz

from config.strategy_params import RANDOM_DECISION
from src.utils.logger import get_logger

logger = get_logger()


class DecisionEngine:
    """
    Random decision engine for trade entry.
    Uses cryptographic randomness to make entry decisions unpredictable.
    """
    
    def __init__(self):
        """Initialize decision engine."""
        self.logger = get_logger()
        self.entry_probability = RANDOM_DECISION['entry_probability']
        self.use_cryptographic_rng = RANDOM_DECISION['use_cryptographic_rng']
        self.min_confidence = RANDOM_DECISION['min_confidence']
        
        self.decision_history = []
    
    def generate_random_value(self) -> float:
        """
        Generate random value between 0 and 1.
        
        Returns:
            Random value (0.0 to 1.0)
        """
        if self.use_cryptographic_rng:
            # Use cryptographic random number generator
            random_bytes = secrets.token_bytes(4)
            random_int = int.from_bytes(random_bytes, byteorder='big')
            return random_int / (2**32 - 1)
        else:
            # Use pseudo-random generator
            return random.random()
    
    def should_enter_trade(
        self,
        confidence: float = 1.0,
        custom_probability: Optional[float] = None
    ) -> tuple[bool, float]:
        """
        Decide whether to enter a trade based on randomness.
        
        Args:
            confidence: Confidence level (0.0 to 1.0)
            custom_probability: Custom entry probability (overrides default)
            
        Returns:
            Tuple of (should_enter, random_value)
        """
        # Check minimum confidence
        if confidence < self.min_confidence:
            self.logger.debug(f"Confidence {confidence} below minimum {self.min_confidence}")
            return False, 0.0
        
        # Generate random value
        random_value = self.generate_random_value()
        
        # Use custom probability if provided
        probability = custom_probability if custom_probability is not None else self.entry_probability
        
        # Make decision
        should_enter = random_value < probability
        
        # Log decision
        self.decision_history.append({
            'timestamp': datetime.now(pytz.UTC),
            'random_value': random_value,
            'probability': probability,
            'confidence': confidence,
            'decision': should_enter
        })
        
        if should_enter:
            self.logger.info(f"Trade ENTERED: Random value {random_value:.4f} < {probability:.2f}")
        else:
            self.logger.debug(f"Trade SKIPPED: Random value {random_value:.4f} >= {probability:.2f}")
        
        return should_enter, random_value
    
    def decide_on_bad_luck_moment(
        self,
        bad_luck_moment,
        confidence: float = 1.0
    ) -> tuple[bool, float]:
        """
        Decide whether to enter trade on detected bad luck moment.
        
        Args:
            bad_luck_moment: BadLuckMoment object
            confidence: Confidence level
            
        Returns:
            Tuple of (should_enter, random_value)
        """
        should_enter, random_value = self.should_enter_trade(confidence)
        
        # Update bad luck moment
        bad_luck_moment.accepted = should_enter
        bad_luck_moment.random_value = random_value
        
        return should_enter, random_value
    
    def adjust_entry_probability(self, new_probability: float) -> None:
        """
        Adjust entry probability.
        
        Args:
            new_probability: New probability (0.0 to 1.0)
        """
        if not 0.0 <= new_probability <= 1.0:
            raise ValueError("Probability must be between 0.0 and 1.0")
        
        self.entry_probability = new_probability
        self.logger.info(f"Entry probability adjusted to {new_probability:.2f}")
    
    def get_decision_stats(self) -> dict:
        """
        Get statistics about decisions made.
        
        Returns:
            Dictionary with decision statistics
        """
        if not self.decision_history:
            return {
                'total_decisions': 0,
                'entries': 0,
                'skips': 0,
                'entry_rate': 0.0,
                'avg_random_value': 0.0
            }
        
        total = len(self.decision_history)
        entries = sum(1 for d in self.decision_history if d['decision'])
        skips = total - entries
        entry_rate = entries / total
        avg_random = sum(d['random_value'] for d in self.decision_history) / total
        
        return {
            'total_decisions': total,
            'entries': entries,
            'skips': skips,
            'entry_rate': entry_rate,
            'avg_random_value': avg_random
        }
    
    def get_recent_decisions(self, limit: int = 10) -> list:
        """
        Get recent decisions.
        
        Args:
            limit: Number of recent decisions to return
            
        Returns:
            List of recent decisions
        """
        return self.decision_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear decision history."""
        self.decision_history.clear()
        self.logger.info("Decision history cleared")
    
    def reset_probability(self) -> None:
        """Reset entry probability to default."""
        self.entry_probability = RANDOM_DECISION['entry_probability']
        self.logger.info(f"Entry probability reset to {self.entry_probability:.2f}")
    
    def simulate_decisions(
        self,
        num_simulations: int = 1000,
        probability: Optional[float] = None
    ) -> dict:
        """
        Simulate decisions to understand expected behavior.
        
        Args:
            num_simulations: Number of simulations
            probability: Probability to use (defaults to current)
            
        Returns:
            Dictionary with simulation results
        """
        prob = probability if probability is not None else self.entry_probability
        
        random_values = []
        decisions = []
        
        for _ in range(num_simulations):
            random_val = self.generate_random_value()
            decision = random_val < prob
            
            random_values.append(random_val)
            decisions.append(decision)
        
        entries = sum(decisions)
        entry_rate = entries / num_simulations
        
        return {
            'num_simulations': num_simulations,
            'probability': prob,
            'entries': entries,
            'skips': num_simulations - entries,
            'entry_rate': entry_rate,
            'avg_random_value': sum(random_values) / num_simulations,
            'min_random_value': min(random_values),
            'max_random_value': max(random_values)
        }
