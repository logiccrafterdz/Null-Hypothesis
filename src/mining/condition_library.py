"""
Condition library for the mining platform.

Contains 50+ atomic, vectorizable, trailing-only conditions used by the
random strategy generator. Each condition is a dict spec:

    {'type': 'rsi_lt', 'params': {'period': 14, 'threshold': 30}}

with a fixed valid parameter space per type. Conditions are evaluated against
a pre-computed feature dictionary (shared by all strategies in a session):

    build_features(df) -> F   (dict[str, np.ndarray])
    evaluate_condition(F, cond) -> np.ndarray[bool]

ALL conditions use only information available at the current bar close
(trailing indicators / session clock) — no lookahead, no synthetic data.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.utils.indicators import (
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
)


# --------------------------------------------------------------------------- #
# Parameter spaces (equal for both assets; nothing asset-tuned).
# --------------------------------------------------------------------------- #
LOOKBACKS = [2, 3, 5, 8, 13]                     # breakout/breakdown windows
ROC_PERIODS = [2, 3, 5, 8, 13, 21]
ROC_THRESHOLDS_PCT = [0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
RSI_PERIODS = [5, 14, 21]
RSI_GT = [55, 60, 70, 80]
RSI_LT = [20, 30, 40, 45]
VOL_MA_PERIODS = [10, 20, 50]
VOL_MULTS = [1.2, 1.5, 2.0, 2.5, 3.0]
VOL_Z_PERIODS = [20, 50, 100]
VOL_Z_THRESHOLDS = [1.0, 1.5, 2.0, 2.5, 3.0]
VOL_PCT_PERIODS = [50, 100, 200]
VOL_PCT_GT = [0.8, 0.9, 0.95, 0.98]
VOL_PCT_LT = [0.05, 0.1, 0.2]
ATR_MULTS = [0.5, 1.0, 1.5, 2.0, 3.0]
BODY_RATIOS = [0.3, 0.5, 0.7, 0.9]
BODY_MULTS = [1.0, 1.5, 2.0, 3.0]
NEAR_FRACS = [0.5, 0.7, 0.9]
PRICE_MA_PERIODS = [20, 50, 100, 200]
CONSEC_NS = [2, 3, 4, 5, 8]
HOUR_SPANS = [4, 6, 8, 12]
BARS_SINCE_MIDNIGHT = [8, 16, 32, 48]
ENGULF_MULTS = [1.0, 1.2, 1.5]

WARMUP_BARS = 300  # global start barrier for every strategy and the baseline


# --------------------------------------------------------------------------- #
# Feature pre-computation (one pass, shared by all strategies).
# --------------------------------------------------------------------------- #
def build_features(df: pd.DataFrame) -> dict:
    """Compute every indicator column a condition can reference."""
    df = df[["open", "high", "low", "close", "volume"]]
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    v = df["volume"].values
    n = len(df)
    F = {"open": o, "high": h, "low": l, "close": c, "volume": v}

    prev_h = df["high"].shift(1)
    prev_l = df["low"].shift(1)
    prev_c = df["close"].shift(1)
    prev_o = df["open"].shift(1)
    F["prev_open"] = prev_o.values
    F["prev_high"] = prev_h.values
    F["prev_low"] = prev_l.values
    F["prev_close"] = prev_c.values

    # Candle anatomy (range, body, shadows).
    rng = (h - l)
    body = (c - o).__abs__()
    F["range"] = np.where(rng <= 0, np.nan, rng)
    F["body_ratio"] = np.where(rng <= 0, np.nan, body / np.where(rng <= 0, 1, rng))
    upper = h - np.maximum(c, o)
    lower = np.minimum(c, o) - l
    F["upper_shadow_body"] = np.where(body <= 0, np.nan, upper / np.where(body <= 0, 1, body))
    F["lower_shadow_body"] = np.where(body <= 0, np.nan, lower / np.where(body <= 0, 1, body))
    close_frac = (c - l) / np.where(rng <= 0, 1, rng)
    F["close_frac"] = np.where(rng <= 0, np.nan, close_frac)

    # Inside / outside / gap.
    F["inside_bar"] = ((h <= prev_h) & (l >= prev_l)).values
    F["outside_bar"] = ((h >= prev_h) & (l <= prev_l)).values
    F["gap_up"] = (df["open"] > prev_h).values
    F["gap_down"] = (df["open"] < prev_l).values

    # Breakout / breakdown highs & lows (trailing, previous bars only).
    for lb in LOOKBACKS:
        F[f"prev_high_max_{lb}"] = prev_h.rolling(lb).max().values
        F[f"prev_low_min_{lb}"] = prev_l.rolling(lb).min().values

    # Moving averages of price.
    for p in PRICE_MA_PERIODS:
        F[f"sma_close_{p}"] = calculate_sma(df, p).values
        F[f"ema_close_{p}"] = calculate_ema(df, p).values

    # RSI, ROC, momentum.
    for p in RSI_PERIODS:
        F[f"rsi_{p}"] = calculate_rsi(df, p).values
    for p in ROC_PERIODS:
        roc = c / np.roll(c, p) - 1.0
        roc[:p] = np.nan
        F[f"roc_{p}"] = roc
        F[f"roc_prev_{p}"] = np.roll(roc, 1)
        F[f"roc_prev_{p}"][:p + 1] = np.nan

    # MACD histogram (12/26/9).
    macd_line, signal_line, _ = calculate_macd(df)
    hist = macd_line - signal_line
    F["macd_hist"] = hist.values
    F["macd_hist_prev"] = hist.shift(1).values

    # Bollinger (20, 2).
    try:
        mid, upper_b, lower_b = calculate_bollinger_bands(df, period=20, num_std=2)
        F["bb_upper"] = upper_b.values
        F["bb_lower"] = lower_b.values
    except Exception:
        F["bb_upper"] = np.full(n, np.nan)
        F["bb_lower"] = np.full(n, np.nan)

    # ATR and volatility expansion.
    atr = calculate_atr(df, 14)
    F["atr"] = atr.values
    F["atr_avg"] = atr.shift(1).rolling(14).mean().values

    # Consecutive candles.
    up = (c > np.roll(c, 1))
    up[0] = False
    down = (c < np.roll(c, 1))
    down[0] = False
    for nup in CONSEC_NS:
        F[f"n_up_{nup}"] = pd.Series(up).rolling(nup).sum().values >= nup
        F[f"n_down_{nup}"] = pd.Series(down).rolling(nup).sum().values >= nup

    # Volume baselines.
    for p in VOL_MA_PERIODS:
        F[f"sma_vol_{p}"] = df["volume"].rolling(p).mean().values
        F[f"ema_vol_{p}"] = df["volume"].ewm(span=p, adjust=False).mean().values
    F["vol_prev"] = v.copy()
    F["vol_prev"][1:] = v[:-1]
    F["vol_prev"][0] = np.nan
    # Production-formula volume ratio: current volume vs mean of the previous
    # 20 bars EXCLUDING the current bar (BAD_LUCK_DETECTOR["volume_period"]).
    vol_base = df["volume"].shift(1).rolling(20).mean().replace(0, np.nan)
    F["vol_ratio_prev_20"] = (v / vol_base).values
    for w in VOL_Z_PERIODS:
        mean = df["volume"].rolling(w).mean().values
        std = df["volume"].rolling(w).std().values
        z = np.full(n, np.nan)
        m = (std > 0) & np.isfinite(std)
        z[m] = (v[m] - mean[m]) / std[m]
        F[f"vol_z_{w}"] = z
    for w in VOL_PCT_PERIODS:
        F[f"vol_pct_{w}"] = df["volume"].rolling(w).rank(pct=True).fillna(0.0).values

    # Time context (UTC). Bars are 15-min aligned in the export.
    idx = df.index
    F["hour"] = idx.hour.values
    F["weekday"] = idx.weekday.values
    F["bars_since_midnight"] = (idx.hour * 60 + idx.minute).values // 15

    # Day / year context for metrics (shared by the bulk backtester).
    F["_index"] = idx
    F["times"] = idx.values
    F["year"] = idx.year.to_numpy(dtype=np.int64)
    F["day_idx"] = (idx.normalize() - idx.normalize()[0]).days.to_numpy(
        dtype=np.int64)

    return F


# --------------------------------------------------------------------------- #
# Conditions: NOTES on comparisons -> NaN is treated as False (numpy semantics).
# --------------------------------------------------------------------------- #
def _gt(a, b):
    return a > b


def _lt(a, b):
    return a < b


CONDITION_TEMPLATES = {
    # ---------------- Price / candle shape ----------------
    "bull_candle": {"params": {}, "desc": "Close > Open (bullish candle)"},
    "bear_candle": {"params": {}, "desc": "Close < Open (bearish candle)"},
    "breakout_high": {"params": {"n": LOOKBACKS},
                      "desc": "Close > highest high of previous {n} bars"},
    "breakdown_low": {"params": {"n": LOOKBACKS},
                      "desc": "Close < lowest low of previous {n} bars"},
    "range_gt_atr": {"params": {"x": ATR_MULTS},
                     "desc": "(High-Low) > ATR * {x} (volatility spike)"},
    "body_ratio_gt": {"params": {"x": BODY_RATIOS},
                      "desc": "(Close-Open)/(High-Low) > {x}"},
    "body_ratio_lt": {"params": {"x": BODY_RATIOS},
                      "desc": "(Close-Open)/(High-Low) < {x}"},
    "upper_shadow_gt_body": {"params": {"x": BODY_MULTS},
                             "desc": "Upper shadow > body * {x}"},
    "lower_shadow_gt_body": {"params": {"x": BODY_MULTS},
                             "desc": "Lower shadow > body * {x}"},
    "close_near_high": {"params": {"x": NEAR_FRACS},
                        "desc": "Close in top {x} of the bar range"},
    "close_near_low": {"params": {"x": NEAR_FRACS},
                       "desc": "Close in bottom {x} of the bar range"},
    "inside_bar": {"params": {}, "desc": "Inside bar (current range inside previous)"},
    "outside_bar": {"params": {}, "desc": "Outside bar"},
    "gap_up": {"params": {}, "desc": "Gap up (open > previous high)"},
    "gap_down": {"params": {}, "desc": "Gap down (open < previous low)"},
    "price_gt_sma": {"params": {"n": PRICE_MA_PERIODS},
                     "desc": "Close > SMA({n})"},
    "price_lt_sma": {"params": {"n": PRICE_MA_PERIODS},
                     "desc": "Close < SMA({n})"},
    "price_gt_ema": {"params": {"n": PRICE_MA_PERIODS},
                     "desc": "Close > EMA({n})"},
    "price_lt_ema": {"params": {"n": PRICE_MA_PERIODS},
                     "desc": "Close < EMA({n})"},

    # ---------------- Momentum ----------------
    "drop_gt": {"params": {"x": ROC_THRESHOLDS_PCT},
                "desc": "1-bar close drop > {x}% (panic bar)"},
    "rise_gt": {"params": {"x": ROC_THRESHOLDS_PCT},
                "desc": "1-bar close rise > {x}% (surge bar)"},
    "vol_ratio_gt": {"params": {"x": VOL_MULTS},
                     "desc": "Volume > prior bar volume * {x} (sheriff spike)"},
    "vol_ratio_prev": {"params": {"x": VOL_MULTS},
                       "desc": "Volume > {x}x the mean of the previous 20 bars"
                               " (production detector formula)"},
    "roc_gt": {"params": {"n": ROC_PERIODS, "x": ROC_THRESHOLDS_PCT},
               "desc": "ROC(close,{n}) > {x}%"},
    "roc_lt": {"params": {"n": ROC_PERIODS, "x": ROC_THRESHOLDS_PCT},
               "desc": "ROC(close,{n}) < -{x}%"},
    "rsi_gt": {"params": {"n": RSI_PERIODS, "x": RSI_GT},
               "desc": "RSI({n}) > {x}"},
    "rsi_lt": {"params": {"n": RSI_PERIODS, "x": RSI_LT},
               "desc": "RSI({n}) < {x}"},
    "macd_hist_gt0": {"params": {}, "desc": "MACD histogram > 0"},
    "macd_hist_lt0": {"params": {}, "desc": "MACD histogram < 0"},
    "macd_hist_rising": {"params": {}, "desc": "MACD histogram rising"},
    "macd_hist_falling": {"params": {}, "desc": "MACD histogram falling"},
    "bbc_upper": {"params": {}, "desc": "Close above upper Bollinger band"},
    "bbc_lower": {"params": {}, "desc": "Close below lower Bollinger band"},
    "roc_accel": {"params": {"n": ROC_PERIODS},
                  "desc": "Momentum increasing (ROC({n}) > prior ROC)"},
    "atr_spike": {"params": {"x": [1.2, 1.5, 2.0, 2.5]},
                  "desc": "ATR > {x}x its trailing average"},
    "n_up_candles": {"params": {"n": CONSEC_NS},
                     "desc": "{n} consecutive rising closes"},
    "n_down_candles": {"params": {"n": CONSEC_NS},
                       "desc": "{n} consecutive falling closes"},

    # ---------------- Volume ----------------
    "vol_gt_sma": {"params": {"p": VOL_MA_PERIODS, "x": VOL_MULTS},
                   "desc": "Volume > SMA({p}) * {x}"},
    "vol_lt_sma": {"params": {"p": VOL_MA_PERIODS, "x": VOL_MULTS},
                   "desc": "Volume < SMA({p}) * {x}"},
    "vol_gt_ema": {"params": {"p": VOL_MA_PERIODS, "x": VOL_MULTS},
                   "desc": "Volume > EMA({p}) * {x}"},
    "vol_lt_ema": {"params": {"p": VOL_MA_PERIODS, "x": VOL_MULTS},
                   "desc": "Volume < EMA({p}) * {x}"},
    "vol_z_gt": {"params": {"w": VOL_Z_PERIODS, "x": VOL_Z_THRESHOLDS},
                 "desc": "Volume z-score({w}) > {x}"},
    "vol_z_lt": {"params": {"w": VOL_Z_PERIODS, "x": VOL_Z_THRESHOLDS},
                 "desc": "Volume z-score({w}) < -{x}"},
    "vol_pct_gt": {"params": {"w": VOL_PCT_PERIODS, "q": VOL_PCT_GT},
                   "desc": "Volume above {q} of trailing {w} bars"},
    "vol_pct_lt": {"params": {"w": VOL_PCT_PERIODS, "q": VOL_PCT_LT},
                   "desc": "Volume below {q} of trailing {w} bars"},
    "vol_rising": {"params": {}, "desc": "Volume rising vs prior bar"},
    "vol_falling": {"params": {}, "desc": "Volume falling vs prior bar"},

    # ---------------- Time ----------------
    "hour_between": {"params": {"a": list(range(0, 24)), "span": HOUR_SPANS},
                     "desc": "UTC hour in [{a},{a}+{span})"},
    "weekday_in": {"params": {"days": [[0, 1], [1, 2], [2, 3], [3, 4],
                                        [0, 4], [0, 1, 2], [2, 3, 4]]},
                   "desc": "Trading day in {days}"},
    "bars_since_midnight_lt": {"params": {"x": BARS_SINCE_MIDNIGHT},
                               "desc": "Bars since UTC midnight < {x}"},
    "bars_since_midnight_gt": {"params": {"x": BARS_SINCE_MIDNIGHT},
                               "desc": "Bars since UTC midnight > {x}"},

    # ---------------- Patterns ----------------
    "bull_engulf": {"params": {"x": ENGULF_MULTS},
                    "desc": "Bullish engulfing bar"},
    "bear_engulf": {"params": {"x": ENGULF_MULTS},
                    "desc": "Bearish engulfing bar"},
    "hammer": {"params": {}, "desc": "Hammer-like lower-wick candle"},
    "doji": {"params": {}, "desc": "Doji-like tiny-body candle"},
    "uptrend_high": {"params": {"n": LOOKBACKS},
                     "desc": "Higher highs: last {n} highs all higher"},
    "downtrend_low": {"params": {"n": LOOKBACKS},
                      "desc": "Lower lows: last {n} lows all lower"},
}

CONDITION_TYPES = sorted(CONDITION_TEMPLATES.keys())


def describe(cond: dict) -> str:
    """Human-readable description of one condition."""
    t = cond["type"]
    p = cond.get("params", {})
    template = CONDITION_TEMPLATES[t]["desc"]
    try:
        return template.format(**p)
    except Exception:
        return template


def evaluate_condition(F: dict, cond: dict) -> np.ndarray:
    """Return a boolean mask for *one* condition over the whole feature grid."""
    t = cond["type"]
    p = cond.get("params", {})
    body = np.abs(F["close"] - F["open"])
    rng = F["range"]

    if t == "bull_candle":
        return F["close"] > F["open"]
    if t == "bear_candle":
        return F["close"] < F["open"]
    if t == "breakout_high":
        return F["close"] > F[f"prev_high_max_{p['n']}"]
    if t == "breakdown_low":
        return F["close"] < F[f"prev_low_min_{p['n']}"]
    if t == "range_gt_atr":
        return rng > F["atr"] * p["x"]
    if t == "body_ratio_gt":
        return F["body_ratio"] > p["x"]
    if t == "body_ratio_lt":
        return F["body_ratio"] < p["x"]
    if t == "upper_shadow_gt_body":
        return F["upper_shadow_body"] > p["x"]
    if t == "lower_shadow_gt_body":
        return F["lower_shadow_body"] > p["x"]
    if t == "close_near_high":
        return F["close_frac"] > p["x"]
    if t == "close_near_low":
        return F["close_frac"] < p["x"]
    if t == "inside_bar":
        return F["inside_bar"]
    if t == "outside_bar":
        return F["outside_bar"]
    if t == "gap_up":
        return F["gap_up"]
    if t == "gap_down":
        return F["gap_down"]
    if t == "price_gt_sma":
        return F["close"] > F[f"sma_close_{p['n']}"]
    if t == "price_lt_sma":
        return F["close"] < F[f"sma_close_{p['n']}"]
    if t == "price_gt_ema":
        return F["close"] > F[f"ema_close_{p['n']}"]
    if t == "price_lt_ema":
        return F["close"] < F[f"ema_close_{p['n']}"]

    if t == "drop_gt":
        return F["close"] < F["prev_close"] * (1 - p["x"] / 100.0)
    if t == "rise_gt":
        return F["close"] > F["prev_close"] * (1 + p["x"] / 100.0)
    if t == "vol_ratio_gt":
        return F["volume"] > F["vol_prev"] * p["x"]
    if t == "vol_ratio_prev":
        return F["vol_ratio_prev_20"] > p["x"]
    if t == "roc_gt":
        return F[f"roc_{p['n']}"] > p["x"] / 100.0
    if t == "roc_lt":
        return F[f"roc_{p['n']}"] < -p["x"] / 100.0
    if t == "rsi_gt":
        return F[f"rsi_{p['n']}"] > p["x"]
    if t == "rsi_lt":
        return F[f"rsi_{p['n']}"] < p["x"]
    if t == "macd_hist_gt0":
        return F["macd_hist"] > 0
    if t == "macd_hist_lt0":
        return F["macd_hist"] < 0
    if t == "macd_hist_rising":
        return F["macd_hist"] > F["macd_hist_prev"]
    if t == "macd_hist_falling":
        return F["macd_hist"] < F["macd_hist_prev"]
    if t == "bbc_upper":
        return F["close"] > F["bb_upper"]
    if t == "bbc_lower":
        return F["close"] < F["bb_lower"]
    if t == "roc_accel":
        return F[f"roc_{p['n']}"] > F[f"roc_prev_{p['n']}"]
    if t == "atr_spike":
        return F["atr"] > F["atr_avg"] * p["x"]
    if t == "n_up_candles":
        return F[f"n_up_{p['n']}"]
    if t == "n_down_candles":
        return F[f"n_down_{p['n']}"]

    if t == "vol_gt_sma":
        return F["volume"] > F[f"sma_vol_{p['p']}"] * p["x"]
    if t == "vol_lt_sma":
        return F["volume"] < F[f"sma_vol_{p['p']}"] * p["x"]
    if t == "vol_gt_ema":
        return F["volume"] > F[f"ema_vol_{p['p']}"] * p["x"]
    if t == "vol_lt_ema":
        return F["volume"] < F[f"ema_vol_{p['p']}"] * p["x"]
    if t == "vol_z_gt":
        return F[f"vol_z_{p['w']}"] > p["x"]
    if t == "vol_z_lt":
        return F[f"vol_z_{p['w']}"] < -p["x"]
    if t == "vol_pct_gt":
        return F[f"vol_pct_{p['w']}"] > p["q"]
    if t == "vol_pct_lt":
        return F[f"vol_pct_{p['w']}"] < p["q"]
    if t == "vol_rising":
        return F["volume"] > F["vol_prev"]
    if t == "vol_falling":
        return F["volume"] < F["vol_prev"]

    if t == "hour_between":
        a = p["a"]
        b = min(a + p["span"], 24)
        return (F["hour"] >= a) & (F["hour"] < b)
    if t == "weekday_in":
        days = np.asarray(p["days"])
        return np.isin(F["weekday"], days)
    if t == "bars_since_midnight_lt":
        return F["bars_since_midnight"] < p["x"]
    if t == "bars_since_midnight_gt":
        return F["bars_since_midnight"] > p["x"]

    if t == "bull_engulf":
        pc, po = F["prev_close"], F["prev_open"]
        return ((F["close"] > F["open"]) & (pc < po) &
                (F["close"] >= po * (2 - p["x"])) & (F["open"] <= pc * p["x"]))
    if t == "bear_engulf":
        pc, po = F["prev_close"], F["prev_open"]
        return ((F["close"] < F["open"]) & (pc > po) &
                (F["close"] <= po * (2 - p["x"])) & (F["open"] >= pc * p["x"]))
    if t == "hammer":
        return ((F["lower_shadow_body"] > 2.0) & (F["body_ratio"] < 0.5))
    if t == "doji":
        return F["body_ratio"] < 0.15
    if t == "uptrend_high":
        h = F["high"]
        prev = np.roll(h, 1)
        prev[0] = np.nan
        return (h > prev) & (prev > np.roll(prev, 1))
    if t == "downtrend_low":
        lw = F["low"]
        prev = np.roll(lw, 1)
        prev[0] = np.nan
        return (lw < prev) & (prev < np.roll(prev, 1))

    raise ValueError(f"Unknown condition type: {t}")


def evaluate_operator(F: dict, conditions: list, operator: str) -> np.ndarray:
    """Combine a list of condition masks with and / or / mixed logic.

    'and':  all conditions must be true.
    'or':   any condition true.
    'mixed': conditions are split into two groups; each group is OR'd and the
             two group-masks are AND'd (mimics "(A or B) and (C or D)").
    """
    masks = [evaluate_condition(F, cond) for cond in conditions]
    if operator == "and":
        out = np.ones(len(F["close"]), dtype=bool)
        for m in masks:
            out &= m
        return out
    if operator == "or":
        out = np.zeros(len(F["close"]), dtype=bool)
        for m in masks:
            out |= m
        return out
    if operator == "mixed":
        half = max(1, len(conditions) // 2)
        left = np.zeros(len(F["close"]), dtype=bool)
        for m in masks[:half]:
            left |= m
        right = np.zeros(len(F["close"]), dtype=bool)
        for m in masks[half:]:
            right |= m
        return left & right
    raise ValueError(f"Unknown operator: {operator}")


def load_real_data(asset: str, timeframe: str = "M15") -> pd.DataFrame:
    """Load a real exported CSV in the standard format (UTC, comment header)."""
    path = Path(__file__).resolve().parents[2] / "data" / "raw" / \
        f"{asset}_{timeframe}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Real data not found: {path}")
    df = pd.read_csv(path, comment="#", index_col=0, parse_dates=True)
    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC")
    else:
        df.index = df.index.tz_localize("UTC")
    return df[["open", "high", "low", "close", "volume"]].astype(float)