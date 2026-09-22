"""
Regression tests for trading-session timezone consistency.
Sessions and news blackouts must be evaluated in UTC regardless of
whether the input datetime is naive or aware and regardless of the
host machine's local timezone.
"""

import unittest
from datetime import datetime
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytz

from src.utils.helpers import ensure_utc, is_trading_hours
from config.settings import MARKET_SESSION_TIMEZONE


class TestEnsureUtc(unittest.TestCase):
    """ensure_utc must interpret naive datetimes as UTC."""

    def test_naive_is_interpreted_as_utc(self):
        naive = datetime(2026, 9, 21, 12, 0)  # Monday
        result = ensure_utc(naive)
        self.assertEqual(result.tzinfo, pytz.UTC)
        self.assertEqual(result.hour, 12)

    def test_aware_utc_is_identity(self):
        aware = datetime(2026, 9, 21, 12, 0, tzinfo=pytz.UTC)
        self.assertEqual(ensure_utc(aware), aware)

    def test_non_utc_aware_is_converted(self):
        est = pytz.timezone('US/Eastern')
        aware = est.localize(datetime(2026, 9, 21, 8, 0))
        result = ensure_utc(aware)
        self.assertEqual(result.tzinfo, pytz.UTC)
        self.assertEqual(result.hour, 12)


class TestTradingHoursConsistency(unittest.TestCase):
    """Session windows behave identically for naive and aware inputs."""

    def test_monday_full_session(self):
        monday = datetime(2026, 9, 21, 10, 0)
        self.assertTrue(is_trading_hours(monday, 'XAUUSD'))

    def test_sunday_cutoff_at_17_utc(self):
        sunday_before = datetime(2026, 9, 20, 16, 59)
        sunday_open = datetime(2026, 9, 20, 17, 0)
        self.assertFalse(is_trading_hours(sunday_before, 'EURUSD'))
        self.assertTrue(is_trading_hours(sunday_open, 'EURUSD'))

    def test_friday_close_at_17_utc(self):
        friday_open = datetime(2026, 9, 18, 16, 59)
        friday_closed = datetime(2026, 9, 18, 17, 0)
        self.assertTrue(is_trading_hours(friday_open, 'GBPJPY'))
        self.assertFalse(is_trading_hours(friday_closed, 'GBPJPY'))

    def test_aware_and_naive_agree(self):
        naive = datetime(2026, 9, 18, 16, 0)
        aware = naive.replace(tzinfo=pytz.UTC)
        self.assertEqual(
            is_trading_hours(naive, 'XAUUSD'),
            is_trading_hours(aware, 'XAUUSD')
        )

    def test_session_timezone_is_utc(self):
        self.assertEqual(MARKET_SESSION_TIMEZONE, "UTC")


if __name__ == '__main__':
    unittest.main()