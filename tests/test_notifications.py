"""
Unit tests for non-blocking Telegram notification delivery.
notify_* must never block the strategy loop on the Telegram API.
"""

import time
import unittest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.notifications import NotificationManager


class TestNotificationsNonBlocking(unittest.TestCase):
    """notify_* paths must enqueue and return without network I/O."""

    def test_notify_returns_immediately(self):
        mgr = NotificationManager()
        mgr.enabled = True
        mgr.bot = Mock()
        mgr.chat_id = "TEST_CHAT"

        with patch.object(mgr, '_ensure_worker'):
            start = time.monotonic()
            result = mgr.notify_trade_entry(
                asset="XAUUSD",
                direction="LONG",
                entry_price=2000.0,
                size=0.1,
                stop_loss=1990.0,
                take_profit=2060.0
            )
            elapsed = time.monotonic() - start

        # Accepted for delivery, returned almost instantly, no network call.
        self.assertTrue(result)
        self.assertLess(elapsed, 0.5)
        self.assertEqual(mgr._queue.qsize(), 1)
        self.assertIn("TRADE ENTRY", mgr._queue.get())
        mgr.bot.send_message.assert_not_called()

    def test_notify_disabled_returns_false(self):
        mgr = NotificationManager()
        mgr.enabled = False
        mgr.bot = None

        start = time.monotonic()
        result = mgr.notify_risk_event(
            event_type="Test", details="unit", severity="INFO"
        )
        elapsed = time.monotonic() - start

        self.assertFalse(result)
        self.assertLess(elapsed, 0.5)
        self.assertEqual(mgr._queue.qsize(), 0)

    def test_worker_not_started_when_disabled(self):
        mgr = NotificationManager()
        mgr.enabled = False
        mgr.bot = None
        mgr.notify_error(error_type="Test", error_message="unit")
        self.assertFalse(mgr._worker_started)

    def test_shutdown_is_idempotent(self):
        mgr = NotificationManager()
        mgr.shutdown()
        mgr.shutdown()


if __name__ == '__main__':
    unittest.main()