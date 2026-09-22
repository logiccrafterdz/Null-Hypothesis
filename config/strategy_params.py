"""
Strategy Parameters for Phoenix Protocol Bad Luck Moment Strategy
All strategy-specific parameters are configurable here.
"""

from typing import Dict, Any

# Bad Luck Moment Detector Parameters
BAD_LUCK_DETECTOR = {
    # Price drop threshold (3% by default)
    "drop_threshold": 0.03,
    
    # Volume spike multiplier (2.0x average volume)
    "volume_multiplier": 2.0,
    
    # ATR spike multiplier (1.5x average ATR)
    "atr_multiplier": 1.5,
    
    # ATR period for calculation
    "atr_period": 14,
    
    # Volume averaging period
    "volume_period": 20,
    
    # Minimum bars required before the detector can produce a verdict
    # (single source of truth for warmup across live and backtesting)
    "warmup_bars": 30,
    
    # Reversal candle patterns to detect
    "reversal_patterns": [
        "hammer",
        "doji",
        "engulfing_bullish",
        "morning_star",
        "piercing",
    ],
}

# Random Decision Engine Parameters
RANDOM_DECISION = {
    # Entry probability (0.0 to 1.0) - higher = more trades
    "entry_probability": 0.6,
    
    # Use cryptographic random number generator
    "use_cryptographic_rng": True,
    
    # Minimum confidence threshold
    "min_confidence": 0.5,
}

# Trade Management Parameters
TRADE_MANAGEMENT = {
    # Stop loss percentage (1.5%)
    "stop_loss_pct": 0.015,
    
    # Take profit percentage (3%) - Risk:Reward = 1:2
    "take_profit_pct": 0.03,
    
    # Enable trailing stop
    "trailing_stop": True,
    
    # Trailing stop activation threshold (1.5% profit)
    "trailing_activation_pct": 0.015,
    
    # Trailing stop distance (0.5% from current price)
    "trailing_distance_pct": 0.005,
    
    # Maximum trade duration in candles
    "max_duration_candles": 15,
    
    # Position size risk per trade (2% of capital)
    "position_size_risk": 0.02,
    
    # Order type (market or pending)
    "order_type": "market",  # Options: market, pending
}

# Risk Management Parameters
RISK_MANAGEMENT = {
    # Maximum daily loss percentage (5%)
    "max_daily_loss": 0.05,
    
    # Maximum weekly loss percentage (10%)
    "max_weekly_loss": 0.10,
    
    # Maximum open trades at once
    "max_open_trades": 2,
    
    # Cooldown after consecutive losses (number of trades to wait)
    "cooldown_after_loss": 3,
    
    # Maximum correlation between positions (0.0 to 1.0)
    "max_correlation": 0.7,
    
    # Maximum position size per asset (percentage of capital)
    "max_position_size_per_asset": 0.05,
    
    # Use equity-based or balance-based risk calculation
    "risk_based_on": "equity",  # Options: equity, balance
}

# News Filter Parameters
NEWS_FILTER = {
    # Enable news filter
    "enabled": True,
    
    # Minutes before news to avoid trading
    "avoid_before_news": 30,
    
    # Minutes after news to avoid trading
    "avoid_after_news": 30,
    
    # High impact news events to avoid
    "high_impact_events": [
        "FOMC",
        "NFP",
        "CPI",
        "GDP",
        "ECB",
        "BOE",
        "BOJ",
    ],
}

# Trend Filter Parameters (Optional additional filter)
TREND_FILTER = {
    # Enable trend filter
    "enabled": False,
    
    # Trend indicator (EMA, SMA, etc.)
    "trend_indicator": "EMA",
    
    # Trend period
    "trend_period": 200,
    
    # Only trade in trend direction
    "trade_with_trend": True,
}

# Volatility Filter Parameters (Optional additional filter)
VOLATILITY_FILTER = {
    # Enable volatility filter
    "enabled": False,
    
    # Minimum ATR for trading
    "min_atr": 0.001,
    
    # Maximum ATR for trading (avoid extreme volatility)
    "max_atr": 0.01,
}

# Backtesting Parameters
BACKTESTING_PARAMS = {
    # Test period (years)
    "test_period_years": 5,
    
    # Walk-forward window size (months)
    "walk_forward_window": 6,
    
    # Walk-forward step size (months)
    "walk_forward_step": 3,
    
    # Monte Carlo simulations
    "monte_carlo_simulations": 1000,
    
    # In-sample percentage
    "in_sample_pct": 0.7,
    
    # Minimum trades for statistical significance
    "min_trades": 100,
}

# Success Criteria
SUCCESS_CRITERIA = {
    "min_win_rate": 0.60,  # 60%
    "min_profit_factor": 2.0,
    "max_drawdown": 0.15,  # 15%
    "min_sharpe_ratio": 0.5,
    "min_trades": 100,
}

# Symbol metadata for MT5 position sizing (lots)
# contract_size: units of the underlying instrument per 1.0 lot
# min_lot / max_lot / lot_step: broker trading volume constraints
# pip_location: decimal places for pip calculations
SYMBOL_METADATA = {
    "XAUUSD": {
        "contract_size": 100,
        "min_lot": 0.01,
        "max_lot": 50.0,
        "lot_step": 0.01,
        "pip_location": 1,
    },
    "EURUSD": {
        "contract_size": 100000,
        "min_lot": 0.01,
        "max_lot": 50.0,
        "lot_step": 0.01,
        "pip_location": 4,
    },
    "GBPJPY": {
        "contract_size": 100000,
        "min_lot": 0.01,
        "max_lot": 50.0,
        "lot_step": 0.01,
        "pip_location": 2,
    },
}
