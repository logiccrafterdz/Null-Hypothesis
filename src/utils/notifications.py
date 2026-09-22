"""
Notification System for Phoenix Protocol Trading System
Handles Telegram notifications for trading events.
"""

import asyncio
import queue
import threading
from typing import Optional, Dict, Any
from datetime import datetime

try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

from config.settings import TELEGRAM_ENABLED, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN
from src.utils.logger import get_logger

logger = get_logger()


class NotificationManager:
    """Manages trading notifications via Telegram.

    Delivery happens on a background worker thread so the strategy and
    trade-execution loops never block waiting on the Telegram API.
    """

    def __init__(self):
        """Initialize notification manager."""
        self.enabled = TELEGRAM_ENABLED and TELEGRAM_AVAILABLE
        self.chat_id = TELEGRAM_CHAT_ID
        self.bot_token = TELEGRAM_TOKEN
        self.bot = None
        self._queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self._worker_started = False
        self._worker = None

        if self.enabled and self.bot_token:
            try:
                self.bot = Bot(token=self.bot_token)
                logger.info("Telegram notification system initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Telegram bot: {e}")
                self.enabled = False

    async def send_message(self, message: str) -> bool:
        """
        Send message via Telegram.

        Args:
            message: Message to send

        Returns:
            True if successful
        """
        if not self.enabled or not self.bot or not self.chat_id:
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram message sent: {message[:50]}...")
            return True
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            return False

    def _ensure_worker(self) -> None:
        """Start the background sender thread on first use."""
        if not self._worker_started:
            self._worker_started = True
            self._worker = threading.Thread(
                target=self._sender_loop,
                daemon=True,
                name="telegram-notifier"
            )
            self._worker.start()

    def _sender_loop(self) -> None:
        """Drain the message queue and deliver asynchronously in background."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while True:
            message = self._queue.get()
            if message is None:
                break
            try:
                loop.run_until_complete(self.send_message(message))
            except Exception as e:
                logger.error(f"Notification sender error: {e}")

    def _enqueue(self, message: str) -> bool:
        """
        Queue a message for non-blocking delivery.

        Args:
            message: Message to send

        Returns:
            True if the message was accepted for delivery
        """
        if not self.enabled or not self.bot or not self.chat_id:
            return False
        self._ensure_worker()
        self._queue.put(message)
        return True

    def shutdown(self) -> None:
        """Stop the background sender thread (idempotent)."""
        if self._worker_started:
            self._queue.put(None)
            if self._worker:
                self._worker.join(timeout=2.0)
            self._worker_started = False

    def send_sync(self, message: str) -> bool:
        """
        Send message synchronously (wrapper for async).

        Args:
            message: Message to send

        Returns:
            True if successful
        """
        if not self.enabled:
            return False

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.send_message(message))
    
    def notify_trade_entry(
        self,
        asset: str,
        direction: str,
        entry_price: float,
        size: float,
        stop_loss: float,
        take_profit: float,
        strategy: str = "Bad Luck Moment"
    ) -> bool:
        """
        Notify about trade entry.
        
        Args:
            asset: Asset symbol
            direction: Trade direction (LONG/SHORT)
            entry_price: Entry price
            size: Position size
            stop_loss: Stop loss price
            take_profit: Take profit price
            strategy: Strategy name
            
        Returns:
            True if successful
        """
        message = f"""
🚀 <b>TRADE ENTRY</b> 🚀

📊 <b>Asset:</b> {asset}
📈 <b>Direction:</b> {direction}
💰 <b>Entry Price:</b> {entry_price:.5f}
📏 <b>Position Size:</b> {size:.4f}
🛑 <b>Stop Loss:</b> {stop_loss:.5f}
🎯 <b>Take Profit:</b> {take_profit:.5f}
🧠 <b>Strategy:</b> {strategy}
⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self._enqueue(message)
    
    def notify_trade_exit(
        self,
        asset: str,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str = "TP/SL Hit"
    ) -> bool:
        """
        Notify about trade exit.
        
        Args:
            asset: Asset symbol
            exit_price: Exit price
            pnl: Profit/Loss amount
            pnl_pct: Profit/Loss percentage
            reason: Exit reason
            
        Returns:
            True if successful
        """
        emoji = "✅" if pnl > 0 else "❌"
        message = f"""
{emoji} <b>TRADE EXIT</b> {emoji}

📊 <b>Asset:</b> {asset}
💰 <b>Exit Price:</b> {exit_price:.5f}
💵 <b>PnL:</b> {pnl:.2f} ({pnl_pct:.2f}%)
📝 <b>Reason:</b> {reason}
⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self._enqueue(message)
    
    def notify_bad_luck_moment(
        self,
        asset: str,
        conditions: Dict[str, Any],
        accepted: bool,
        random_value: Optional[float] = None
    ) -> bool:
        """
        Notify about bad luck moment detection.
        
        Args:
            asset: Asset symbol
            conditions: Detected conditions
            accepted: Whether trade was accepted
            random_value: Random decision value (if applicable)
            
        Returns:
            True if successful
        """
        status = "✅ ACCEPTED" if accepted else "❌ REJECTED"
        message = f"""
🎲 <b>BAD LUCK MOMENT DETECTED</b> 🎲

📊 <b>Asset:</b> {asset}
📋 <b>Status:</b> {status}
📉 <b>Price Drop:</b> {conditions.get('price_drop', 0):.2%}
📊 <b>Volume Spike:</b> {conditions.get('volume_spike', 0):.2f}x
📈 <b>Volatility Spike:</b> {conditions.get('volatility_spike', 0):.2f}x
🕯️ <b>Reversal Pattern:</b> {conditions.get('reversal_pattern', 'No')}
"""
        if random_value is not None:
            message += f"\n🎲 <b>Random Value:</b> {random_value:.4f}"
        
        return self._enqueue(message)
    
    def notify_risk_event(
        self,
        event_type: str,
        details: str,
        severity: str = "WARNING"
    ) -> bool:
        """
        Notify about risk management event.
        
        Args:
            event_type: Type of risk event
            details: Event details
            severity: Severity level (INFO, WARNING, CRITICAL)
            
        Returns:
            True if successful
        """
        emoji = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "CRITICAL": "🚨"
        }.get(severity, "ℹ️")
        
        message = f"""
{emoji} <b>RISK EVENT: {event_type}</b> {emoji}

📝 <b>Details:</b> {details}
⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self._enqueue(message)
    
    def notify_daily_report(
        self,
        trades: int,
        win_rate: float,
        pnl: float,
        max_drawdown: float
    ) -> bool:
        """
        Send daily performance report.
        
        Args:
            trades: Number of trades
            win_rate: Win rate percentage
            pnl: Total PnL
            max_drawdown: Maximum drawdown
            
        Returns:
            True if successful
        """
        message = f"""
📊 <b>DAILY PERFORMANCE REPORT</b> 📊

📈 <b>Trades:</b> {trades}
🎯 <b>Win Rate:</b> {win_rate:.2f}%
💰 <b>Total PnL:</b> {pnl:.2f}
📉 <b>Max Drawdown:</b> {max_drawdown:.2f}%
⏰ <b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}
"""
        return self._enqueue(message)
    
    def notify_error(self, error_type: str, error_message: str) -> bool:
        """
        Notify about system error.
        
        Args:
            error_type: Type of error
            error_message: Error message
            
        Returns:
            True if successful
        """
        message = f"""
🚨 <b>SYSTEM ERROR</b> 🚨

🔴 <b>Type:</b> {error_type}
📝 <b>Message:</b> {error_message}
⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self._enqueue(message)


# Global notification manager instance
_notification_manager = None


def get_notification_manager() -> NotificationManager:
    """
    Get or create notification manager instance.
    
    Returns:
        NotificationManager instance
    """
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
