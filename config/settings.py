"""
Global Settings Configuration for Phoenix Protocol Trading System
All configurable parameters are centralized here for easy adjustment.
"""

from typing import Dict, Any
from pathlib import Path
import os

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
REPORTS_DIR = BASE_DIR / "reports"

# Database settings
DATABASE_TYPE = "sqlite"  # Options: sqlite, postgresql
SQLITE_PATH = DATA_DIR / "trading.db"
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "phoenix_protocol"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

# Trading assets and timeframes
ASSETS = {
    "XAUUSD": {"broker": "mt5", "type": "forex"},
    "GBPJPY": {"broker": "mt5", "type": "forex"},
    "EURUSD": {"broker": "mt5", "type": "forex"},
}

TIMEFRAMES = {
    "main": "M15",  # Main analysis timeframe
    "filter": "H1",  # Filter timeframe
    "execution": "M5",  # Entry execution timeframe
}

# Data settings
# local:  read only from data/raw fixtures; fails loudly when absent
#         (seed fixtures with: python main.py --generate-sample-data)
# live:   always fetch from broker
# hybrid: fetch from broker, fall back to cache
DATA_SOURCE = "local"  # Options: local, live, hybrid
DATA_UPDATE_INTERVAL = 60  # seconds
DATA_RETENTION_DAYS = 365

# Logging settings
LOG_LEVEL = "INFO"  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_TO_FILE = True
LOG_TO_CONSOLE = True
LOG_FILE_MAX_SIZE = 10 * 1024 * 1024  # 10 MB
LOG_FILE_BACKUP_COUNT = 5

# News blackout windows configuration
# All windows are expressed in MARKET_SESSION_TIMEZONE (UTC).
MARKET_SESSION_TIMEZONE = "UTC"

NEWS_BLACKOUT_WINDOWS = [
    {
        "day_of_week": 2,  # Wednesday (0=Monday, 6=Sunday)
        "start_hour": 13,  # 1 PM UTC (before FOMC)
        "end_hour": 15,    # 3 PM UTC (after FOMC)
        "timezone": "UTC",
        "reason": "FOMC meetings"
    },
    {
        "day_of_week": 4,  # Friday
        "start_hour": 7,   # 7 AM UTC (before NFP)
        "end_hour": 10,    # 10 AM UTC (after NFP)
        "timezone": "UTC",
        "reason": "NFP releases"
    },
    {
        "day_of_week": 2,  # Wednesday
        "start_hour": 7,   # 7 AM UTC (before CPI)
        "end_hour": 10,    # 10 AM UTC (after CPI)
        "timezone": "UTC",
        "reason": "CPI releases"
    }
]

# Notification settings
TELEGRAM_ENABLED = True
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# Backtesting settings
BACKTESTING_INITIAL_CAPITAL = 10000
BACKTESTING_COMMISSION = 0.0002  # 0.02%
BACKTESTING_SPREAD = 0.0001  # 0.01%
BACKTESTING_SLIPPAGE = 0.0001  # 0.01%

# System settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
TIMEOUT = 30  # seconds

# Paper trading settings
PAPER_TRADING_ENABLED = False
PAPER_TRADING_INITIAL_CAPITAL = 10000

# Dashboard settings
DASHBOARD_HOST = "localhost"
DASHBOARD_PORT = 8501
DASHBOARD_AUTO_REFRESH = 60  # seconds
