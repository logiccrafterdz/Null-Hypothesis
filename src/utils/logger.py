"""
Logging System for Phoenix Protocol Trading System
Provides structured logging with file rotation and console output.
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Optional
import sys

from config.settings import LOGS_DIR, LOG_LEVEL, LOG_TO_FILE, LOG_TO_CONSOLE, LOG_FILE_MAX_SIZE, LOG_FILE_BACKUP_COUNT


class TradingLogger:
    """Custom logger for trading system with structured formatting."""
    
    def __init__(self, name: str = "PhoenixProtocol", log_dir: Optional[Path] = None):
        """
        Initialize trading logger.
        
        Args:
            name: Logger name
            log_dir: Directory for log files (uses settings if not provided)
        """
        self.name = name
        self.log_dir = log_dir or LOGS_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, LOG_LEVEL))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Add file handler if enabled
        if LOG_TO_FILE:
            log_file = self.log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=LOG_FILE_MAX_SIZE,
                backupCount=LOG_FILE_BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        
        # Add console handler if enabled
        if LOG_TO_CONSOLE:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self.logger.error(message, extra=kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self.logger.critical(message, extra=kwargs)
    
    def trade_signal(self, signal_type: str, asset: str, price: float, **kwargs):
        """Log trading signal."""
        message = f"SIGNAL: {signal_type} | Asset: {asset} | Price: {price:.5f}"
        self.logger.info(message, extra={"signal_type": signal_type, "asset": asset, **kwargs})
    
    def trade_entry(self, asset: str, direction: str, entry_price: float, size: float, **kwargs):
        """Log trade entry."""
        message = f"ENTRY: {asset} | {direction} @ {entry_price:.5f} | Size: {size:.4f}"
        self.logger.info(message, extra={"asset": asset, "direction": direction, **kwargs})
    
    def trade_exit(self, asset: str, exit_price: float, pnl: float, **kwargs):
        """Log trade exit."""
        message = f"EXIT: {asset} @ {exit_price:.5f} | PnL: {pnl:.2f}"
        self.logger.info(message, extra={"asset": asset, "pnl": pnl, **kwargs})
    
    def bad_luck_moment(self, asset: str, conditions: dict, accepted: bool, **kwargs):
        """Log bad luck moment detection."""
        message = f"BAD_LUCK: {asset} | Accepted: {accepted} | Conditions: {conditions}"
        self.logger.info(message, extra={"asset": asset, "accepted": accepted, **kwargs})
    
    def risk_event(self, event_type: str, details: str, **kwargs):
        """Log risk management event."""
        message = f"RISK: {event_type} | {details}"
        self.logger.warning(message, extra={"event_type": event_type, **kwargs})


# Global logger instance
_logger_instance = None


def get_logger(name: str = "PhoenixProtocol") -> TradingLogger:
    """
    Get or create logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        TradingLogger instance
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = TradingLogger(name)
    return _logger_instance


def setup_logger(name: str = "PhoenixProtocol", log_dir: Optional[Path] = None) -> TradingLogger:
    """
    Setup and return a new logger instance.
    
    Args:
        name: Logger name
        log_dir: Directory for log files
        
    Returns:
        TradingLogger instance
    """
    return TradingLogger(name, log_dir)
