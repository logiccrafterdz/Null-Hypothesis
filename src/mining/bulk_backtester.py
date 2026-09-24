"""
High-performance bulk backtester for the mining platform.

Replicates the PRODUCTION trade-management semantics (stop / take profit /
trailing stop / max duration / commission / slippage / minimum-lot sizing,
2% risk per trade, max 2 open positions, 5% daily + 10% weekly loss caps and
a 3-trade cooldown) but is driven by arbitrary entry masks instead of the
bad-luck detector. This module is a standalone research engine: it does NOT
modify backtesting/backtester.py or the production pipeline.

The hot path minimises Python work per bar: all indicators and entry masks are
pre-computed as numpy arrays and equity is only recorded where it can actually
change (open positions, filled entries or settle events).
"""

import math
import random

import numpy as np

from config.settings import BACKTESTING_COMMISSION, BACKTESTING_SLIPPAGE
from config.strategy_params import RISK_MANAGEMENT, SYMBOL_METADATA
from src.mining.condition_library import WARMUP_BARS, evaluate_operator


def evaluate_entry_mask(F: dict, entry: dict, seed: int) -> np.ndarray:
    """Build the full-length boolean entry mask for a strategy spec."""
    n = len(F["close"])
    if entry.get("operator") == "random":
        rng = random.Random(seed)
        density = entry.get("density", 0.01)
        mask = np.zeros(n, dtype=bool)
        for i in range(WARMUP_BARS, n):
            mask[i] = rng.random() < density
        return mask
    return evaluate_operator(F, entry["conditions"], entry["operator"])


def _size(capital: float, stop_pct: float, entry_price: float,
          asset: str) -> float:
    """Mirror helpers.calculate_position_size (0.0 => below minimum lot)."""
    meta = SYMBOL_METADATA[asset]
    risk_amount = capital * 0.02
    stop_amount = entry_price * stop_pct
    if stop_amount <= 0:
        return 0.0
    size = risk_amount / stop_amount / meta["contract_size"]
    if size < meta["min_lot"]:
        return 0.0
    return math.floor(size / meta["lot_step"]) * meta["lot_step"]


def _day_equity(visited_idx, visited_eq, day_idx, n_days):
    """Last equity value per day, forward-filled over the full day range."""
    eq = np.full(n_days, np.nan)
    for i, e in zip(visited_idx, visited_eq):
        eq[day_idx[i]] = e
    carry = np.nan
    for d in range(n_days):
        v = eq[d]
        if np.isnan(v):
            eq[d] = carry
        else:
            carry = v
    return eq


def run_strategy(F: dict, spec: dict, capital: float = 10000.0,
                 entry_mask_override=None) -> dict:
    """Simulate one strategy spec over pre-computed features F."""
    n = len(F["close"])
    close = F["close"]
    high = F["high"]
    low = F["low"]
    year = F["year"]
    day_idx = F["day_idx"]
    times = F["times"]
    is_long = spec["direction"] == "LONG"
    sign = 1 if is_long else -1

    ex = spec["exits"]
    stop_pct = ex["stop_loss_pct"]
    tp_pct = ex["take_profit_pct"]
    trailing = ex["trailing"]
    trail_act = ex["trailing_activation_pct"]
    trail_dist = ex["trailing_distance_pct"]
    max_bars = ex["max_duration_bars"]
    max_open = spec["risk"]["max_open"]

    if entry_mask_override is not None:
        mask = entry_mask_override
    else:
        mask = evaluate_entry_mask(F, spec["entry"],
                                   spec.get("generator_seed", 0))

    capital = float(capital)
    init = capital
    daily_pnl = 0.0
    daily_day = -1
    weekly_pnl = 0.0
    week_start = -1
    cooldown = 0

    counters = {"signals": 0, "entries": 0, "size_refusals": 0,
                "max_open_refusals": 0, "cooldown_refusals": 0,
                "daily_refusals": 0, "weekly_refusals": 0}

    # Hot arrays as Python lists (numpy scalar access dominates the loop).
    close_l = close.tolist()
    high_l = high.tolist()
    low_l = low.tolist()
    year_l = year.tolist()
    day_l = day_idx.tolist()
    wd_l = F["weekday"].tolist()

    trades = []
    open_pos = []
    visited_idx = []
    visited_eq = []

    sig_idx = np.flatnonzero(mask)
    sig_idx = sig_idx[sig_idx >= WARMUP_BARS].tolist()
    ptr = 0
    nsig = len(sig_idx)
    counters["signals"] = nsig

    def _open_pnl(ci):
        total = 0.0
        for p in open_pos:
            total += p["size"] * p["contract_size"] * (sign * (ci - p["entry"]))
        return total

    i = WARMUP_BARS
    while i < n:
        incoming_signal = ptr < nsig and sig_idx[ptr] == i
        if not (open_pos or incoming_signal):
            # Fast-forward to the next signal bar (equity constant in between).
            if ptr >= nsig:
                break
            i = sig_idx[ptr]
            d_t = day_l[i]
            if d_t != daily_day:
                daily_pnl = 0.0
                daily_day = d_t
            ws_t = d_t - wd_l[i]
            if ws_t != week_start:
                weekly_pnl = 0.0
                week_start = ws_t
            continue

        d = day_l[i]
        ws = d - wd_l[i]          # day index of this week's Monday

        # --- Risk window rollovers -----------------------------------
        if daily_day == -1:
            daily_day = d
        elif d > daily_day:
            daily_pnl = 0.0
            daily_day = d
        if week_start == -1:
            week_start = ws
        elif ws > week_start:
            weekly_pnl = 0.0
            week_start = ws

        had_positions = len(open_pos) > 0
        settled_this_bar = 0
        ci = close_l[i]
        hi = high_l[i]
        lo = low_l[i]

        # --- Monitor open positions on this bar ----------------------
        keep = []
        for pos in open_pos:
            pos["bars"] += 1
            pnl_pct = sign * (ci - pos["entry"]) / pos["entry"]
            pos["max_profit"] = max(pos["max_profit"], pnl_pct)
            pos["max_loss"] = min(pos["max_loss"], pnl_pct)

            per = pos["entry"]
            if trailing and (pos["trailing"] or pnl_pct >= trail_act):
                if is_long:
                    cand = ci * (1 - trail_dist)
                    if cand > pos["stop"]:
                        pos["stop"] = cand
                        pos["trailing"] = True
                else:
                    cand = ci * (1 + trail_dist)
                    if cand < pos["stop"]:
                        pos["stop"] = cand
                        pos["trailing"] = True

            exit_price = ci
            reason = None
            if is_long:
                if lo <= pos["stop"]:
                    reason = "Trailing Stop" if pos["trailing"] else "Stop Loss"
                    exit_price = pos["stop"]
                elif hi >= pos["tp"]:
                    reason = "Take Profit"
                    exit_price = pos["tp"]
            else:
                if hi >= pos["stop"]:
                    reason = "Trailing Stop" if pos["trailing"] else "Stop Loss"
                    exit_price = pos["stop"]
                elif lo <= pos["tp"]:
                    reason = "Take Profit"
                    exit_price = pos["tp"]
            if reason is None and pos["bars"] >= max_bars:
                reason = "MAX_DURATION_REACHED"
                exit_price = ci

            if reason is None:
                keep.append(pos)
                continue

            notional_sz = pos["size"] * pos["contract_size"]
            ex_px = exit_price * (1 - BACKTESTING_SLIPPAGE) if is_long \
                else exit_price * (1 + BACKTESTING_SLIPPAGE)
            pnl = notional_sz * (ex_px - per) if is_long \
                else notional_sz * (per - ex_px)
            pnl -= notional_sz * ex_px * BACKTESTING_COMMISSION
            trades.append({
                "entry_time": times[pos["i"]], "exit_time": times[i],
                "direction": spec["direction"], "pnl": pnl,
                "pnl_pct": pnl / (per * notional_sz), "reason": reason,
                "bars": pos["bars"], "entry_year": year_l[pos["i"]],
            })
            capital += pnl
            daily_pnl += pnl
            weekly_pnl += pnl
            if pnl < 0:
                cooldown = RISK_MANAGEMENT["cooldown_after_loss"]
            else:
                cooldown = 0
            settled_this_bar += 1
        open_pos = keep

        # --- Entry gate (pure conditions; no random gate here) --------
        entered = False
        if incoming_signal:
            ptr += 1
            if daily_pnl < -capital * RISK_MANAGEMENT["max_daily_loss"]:
                counters["daily_refusals"] += 1
            elif weekly_pnl < -capital * RISK_MANAGEMENT["max_weekly_loss"]:
                counters["weekly_refusals"] += 1
            elif len(open_pos) >= max_open:
                counters["max_open_refusals"] += 1
            elif cooldown > 0:
                counters["cooldown_refusals"] += 1
                cooldown -= 1
            else:
                entry = ci * (1 + BACKTESTING_SLIPPAGE) if is_long \
                    else ci * (1 - BACKTESTING_SLIPPAGE)
                size = _size(capital, stop_pct, entry, spec["asset"])
                if size <= 0:
                    counters["size_refusals"] += 1
                else:
                    open_pos.append({
                        "i": i, "size": size,
                        "contract_size": SYMBOL_METADATA[spec["asset"]]["contract_size"],
                        "entry": entry,
                        "stop": entry * (1 - stop_pct) if is_long
                                else entry * (1 + stop_pct),
                        "tp": entry * (1 + tp_pct) if is_long
                             else entry * (1 - tp_pct),
                        "bars": 0, "trailing": False,
                        "max_profit": 0.0, "max_loss": 0.0,
                    })
                    counters["entries"] += 1
                    entered = True
                    capital -= size * open_pos[-1]["contract_size"] * entry * \
                        BACKTESTING_COMMISSION

        # --- Equity mark (report only where it changes) ---------------
        if had_positions or settled_this_bar or entered:
            visited_idx.append(i)
            visited_eq.append(capital + _open_pnl(ci))

        i += 1

    # Flatten anything still open at the final close.
    for pos in open_pos:
        i = n - 1
        per = pos["entry"]
        ex_px = close_l[i] * (1 - BACKTESTING_SLIPPAGE) if is_long \
            else close_l[i] * (1 + BACKTESTING_SLIPPAGE)
        notional_sz = pos["size"] * pos["contract_size"]
        pnl = notional_sz * (ex_px - per) if is_long \
            else notional_sz * (per - ex_px)
        pnl -= notional_sz * ex_px * BACKTESTING_COMMISSION
        trades.append({
            "entry_time": times[pos["i"]], "exit_time": times[i],
            "direction": spec["direction"], "pnl": pnl,
            "pnl_pct": pnl / (per * notional_sz), "reason": "End of Data",
            "bars": pos["bars"], "entry_year": year_l[pos["i"]],
        })
        capital += pnl

    return _metrics(spec, trades, visited_idx, visited_eq, capital, init,
                    F, day_idx, counters)


def _metrics(spec, trades, visited_idx, visited_eq, capital, init,
             F, day_idx, counters):
    total = len(trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]
    gross_w = sum(t["pnl"] for t in wins)
    gross_l = -sum(t["pnl"] for t in losses)
    pf = gross_w / gross_l if gross_l > 0 else (float("inf") if gross_w > 0 else 0.0)

    # Max drawdown over the visited equity marks.
    dd_pct = 0.0
    peak = init
    for e in visited_eq:
        if e > peak:
            peak = e
        elif e < peak:
            dd_pct = max(dd_pct, (peak - e) / peak)

    # Daily Sharpe + monthly returns.
    sharpe = 0.0
    monthly = {}
    if len(visited_eq) > 3:
        eq_day = _day_equity(visited_idx, visited_eq, day_idx,
                             int(np.nanmax(day_idx)) + 1)
        prev = None
        rets = []
        for v in eq_day:
            if np.isnan(v):
                continue
            if prev is not None and prev != 0:
                rets.append(v / prev - 1.0)
            prev = v
        if rets:
            arr = np.asarray(rets)
            sd = arr.std()
            if sd > 0:
                sharpe = arr.mean() / sd * np.sqrt(252)

        closes = {}
        for i, e in zip(visited_idx, visited_eq):
            t = np.datetime64(F["times"][i], "M")
            ym = f"{int(t.astype('datetime64[Y]').astype('int') + 1970):04d}-" \
                 f"{int(t.astype('datetime64[M]').astype('int') % 12) + 1:02d}"
            closes[ym] = e
        ordered = sorted(closes.items())
        for j in range(1, len(ordered)):
            ym, e = ordered[j]
            _, pe = ordered[j - 1]
            if pe != 0:
                monthly[ym] = e / pe - 1.0

    # Year split by entry year.
    years = {}
    if trades:
        y1 = min(t["entry_year"] for t in trades)
        for yr in sorted(set(t["entry_year"] for t in trades)):
            yt = [t for t in trades if t["entry_year"] == yr]
            yw = sum(1 for t in yt if t["pnl"] > 0)
            yg_w = sum(t["pnl"] for t in yt if t["pnl"] > 0)
            yg_l = -sum(t["pnl"] for t in yt if t["pnl"] < 0)
            ypf = yg_w / yg_l if yg_l > 0 else (float("inf") if yg_w > 0 else 0.0)
            years[yr] = {
                "n": len(yt), "winrate": yw / len(yt), "pf": ypf,
                "sum_pnl": sum(t["pnl"] for t in yt),
                "return_pct": sum(t["pnl"] for t in yt) / init,
            }

    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1

    return {
        "id": spec["id"],
        "asset": spec["asset"],
        "direction": spec["direction"],
        "total_trades": total,
        "winrate": len(wins) / total if total else 0.0,
        "profit_factor": pf,
        "total_return_pct": capital / init - 1.0,
        "max_dd_pct": dd_pct,
        "sharpe": float(sharpe),
        "expectancy": sum(t["pnl"] for t in trades) / total if total else 0.0,
        "avg_win": gross_w / len(wins) if wins else 0.0,
        "avg_loss": gross_l / len(losses) if losses else 0.0,
        "avg_pnl_pct": float(np.mean([t["pnl_pct"] for t in trades]))
                      if total else 0.0,
        "reasons": reasons,
        "monthly": monthly,
        "years": years,
        "long": sum(1 for t in trades if t["direction"] == "LONG"),
        "short": sum(1 for t in trades if t["direction"] == "SHORT"),
        "counters": counters,
        "n_conditions": len(spec["entry"].get("conditions", [])),
        "exit_config": spec["exits"],
    }