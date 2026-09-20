"""
News Filter for Phoenix Protocol Trading System
Filters trading signals around major economic news events.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pytz

from config.strategy_params import NEWS_FILTER
from src.utils.logger import get_logger


class NewsEvent:
    """Represents a news event."""
    
    def __init__(
        self,
        name: str,
        datetime: datetime,
        impact: str = "medium",
        currency: str = "USD"
    ):
        """
        Initialize news event.
        
        Args:
            name: Event name
            datetime: Event datetime
            impact: Impact level (low, medium, high)
            currency: Related currency
        """
        self.name = name
        self.datetime = datetime
        self.impact = impact
        self.currency = currency
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'datetime': self.datetime,
            'impact': self.impact,
            'currency': self.currency
        }


class NewsFilter:
    """
    News filter for trading signals.
    Prevents trading around major economic news events.
    """
    
    def __init__(self):
        """Initialize news filter."""
        self.logger = get_logger()
        self.enabled = NEWS_FILTER['enabled']
        self.avoid_before_news = NEWS_FILTER['avoid_before_news']
        self.avoid_after_news = NEWS_FILTER['avoid_after_news']
        self.high_impact_events = NEWS_FILTER['high_impact_events']
        
        # In production, this would connect to an economic calendar API
        # For now, we'll use a simplified approach
        self.news_events: List[NewsEvent] = []
    
    def add_news_event(self, event: NewsEvent) -> None:
        """
        Add a news event to the filter.
        
        Args:
            event: NewsEvent object
        """
        self.news_events.append(event)
        self.logger.info(f"Added news event: {event.name} at {event.datetime}")
    
    def is_near_news_event(
        self,
        current_time: datetime,
        currency: str = "USD"
    ) -> Tuple[bool, Optional[NewsEvent]]:
        """
        Check if current time is near a news event.
        
        Args:
            current_time: Current datetime
            currency: Currency to check
            
        Returns:
            Tuple of (is_near, event)
        """
        if not self.enabled:
            return False, None
        
        for event in self.news_events:
            # Check if event is relevant to currency
            if event.currency != currency and event.impact != "high":
                continue
            
            # Check if event is high impact
            if event.impact == "high" or any(
                high_event in event.name.upper()
                for high_event in self.high_impact_events
            ):
                # Calculate time difference
                time_diff = abs((current_time - event.datetime).total_seconds() / 60)
                
                if time_diff <= (self.avoid_before_news + self.avoid_after_news):
                    return True, event
        
        return False, None
    
    def check_signal(
        self,
        current_time: datetime,
        currency: str = "USD"
    ) -> Tuple[bool, str]:
        """
        Check if signal passes news filter.
        
        Args:
            current_time: Current datetime
            currency: Currency to check
            
        Returns:
            Tuple of (passes_filter, reason)
        """
        if not self.enabled:
            return True, "News filter disabled"
        
        is_near, event = self.is_near_news_event(current_time, currency)
        
        if is_near and event:
            time_diff = abs((current_time - event.datetime).total_seconds() / 60)
            
            if time_diff <= self.avoid_before_news:
                return False, f"Too close before {event.name} ({time_diff:.0f} min)"
            elif time_diff <= self.avoid_after_news:
                return False, f"Too close after {event.name} ({time_diff:.0f} min)"
        
        return True, "No nearby news events"
    
    def get_upcoming_events(
        self,
        hours_ahead: int = 24
    ) -> List[NewsEvent]:
        """
        Get upcoming news events.
        
        Args:
            hours_ahead: Hours to look ahead
            
        Returns:
            List of upcoming NewsEvent objects
        """
        current_time = datetime.now(pytz.UTC)
        cutoff_time = current_time + timedelta(hours=hours_ahead)
        
        upcoming = [
            event for event in self.news_events
            if current_time <= event.datetime <= cutoff_time
        ]
        
        return sorted(upcoming, key=lambda x: x.datetime)
    
    def clear_events(self) -> None:
        """Clear all news events."""
        self.news_events.clear()
        self.logger.info("Cleared all news events")
    
    def add_fomc_schedule(self) -> None:
        """Add FOMC meeting schedule (simplified)."""
        # In production, this would fetch from an economic calendar
        # For now, just a placeholder
        pass
    
    def add_nfp_schedule(self) -> None:
        """Add NFP release schedule (simplified)."""
        # In production, this would fetch from an economic calendar
        # For now, just a placeholder
        pass
