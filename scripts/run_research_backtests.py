"""
Research exit-simulation for relaxed "bad luck" signal candidates on REAL data.

Phase D of the signal-feasibility study. This is RESEARCH ONLY: it never
changes production configuration or the production backtester. It re-uses the
exact trade-management semantics of backtesting/backtester.py (commission,
slippage, 1.5% stop, 3% take profit, trailing stop, 15-bar max duration,
minimum-lot sizing via calculate_position_size, max 2 open positions, 5%
daily / 10% weekly loss caps and 3-trade cooldown) and the DecisionEngine
entry rule (random value < 0.6), but drives the entry mask directly from the
relaxed threshold candidates produced by scripts/analyze_signal_feasibility.py
and a seeded random generator so the study is reproducible.

It writes: reports/research_candidate_backtests.md
"""

import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (  # noqa: E402
    BACKTESTING_INITIAL_CAPITAL,
    BACKTESTING_COMMISSION,
    BACKTESTING_SLIPPAGE,
)
from config.strategy_params import (  # noqa: E402
    RANDOM_DECISION,
    RISK_MANAGEMENT,
    SUCCESS_CRITERIA,
    SYMBOL_METADATA,
    TRADE_MANAGEMENT,
)
from src.utils.helpers import calculate_position_size  # noqa: E402
from scripts.analyze_signal_feasibility import (  # noqa: E402
    SYMBOLS,
    prepare_features,
    shortlist_configs,
)

CAPITAL_SCENARIOS = [5000, 10000, 25000, 50000, 100000]
SEED_BASE = 2026


class CandidateSim:
    """Research-only sequential trade simulation for one candidate config."""

    def __init__(self, feats: pd.DataFrame, cfg: dict, capital: float):
        self.f = feats
        self.cfg = cfg
        self.capital = float(capital)
        self.initial_capital = float(capital)

        sym, tf = cfg["sym"], cfg["tf"]
        self.contract = SYMBOL_METADATA[sym]["contract_size"]
        self.mask = feats["drop"] >= cfg["drop"]
        if cfg["kind"] == "ratio":
            self.mask &= feats["vol_ratio"] >= cfg["rule"]
        else:
            self.mask &= feats["vol_z"] >= cfg["rule"]
        self.sig_idx = np.flatnonzero(self.mask.values)

        self.stop_pct = TRADE_MANAGEMENT["stop_loss_pct"]
        self.tp_pct = TRADE_MANAGEMENT["take_profit_pct"]
        self.trail_active_pct = TRADE_MANAGEMENT["trailing_activation_pct"]
        self.trail_dist_pct = TRADE_MANAGEMENT["trailing_distance_pct"]
        self.max_bars = TRADE_MANAGEMENT["max_duration_candles"]
        self.max_open = RISK_MANAGEMENT["max_open_trades"]
        self.cooldown = RISK_MANAGEMENT["cooldown_after_loss"]
        self.daily_limit = RISK_MANAGEMENT["max_daily_loss"]
        self.weekly_limit = RISK_MANAGEMENT["max_weekly_loss"]

        # Funnel counters (same names as the production backtester).
        self.signals = 0
        self.random_refusals = 0
        self.size_refusals = 0
        self.max_open_refusals = 0
        self.cooldown_refusals = 0
        self.daily_refusals = 0
        self.weekly_refusals = 0
        self.entries = 0

        self.trades = []
        self.equity = []

        # Risk state.
        self.daily_pnl = 0.0
        self.daily_date = None
        self.weekly_pnl = 0.0
        self.week_start = None
        self.cooldown_left = 0

    def _want_trade(self, i: int, rng: random.Random) -> bool:
        """Edge loop never needs to open on the last bars; mask is precomputed."""
        return bool(self.mask.iloc[i])

    def run(self, seed: int, entry_prob: float) -> dict:
        rng = random.Random(seed)
        closes = self.f["close"].values
        highs = self.f["high"].values
        lows = self.f["low"].values
        idx = self.f.index
        open_pos = []
        self.week_start = idx[0].normalize() - pd.Timedelta(days=idx[0].weekday())

        for i in range(len(self.f)):
            t = idx[i]
            # 1. Monitor open positions (bar i data; they were opened on i-bars
            #    before, exactly like backtester._monitor_positions).
            self._monitor(open_pos, i, closes, highs, lows, t)

            # 2. Risk window rollovers.
            today = t.date()
            if self.daily_date is None:
                self.daily_date = today
            elif today > self.daily_date:
                self.daily_pnl = 0.0
                self.daily_date = today
            ws = t.normalize() - pd.Timedelta(days=t.weekday())
            if ws > self.week_start:
                self.weekly_pnl = 0.0
                self.week_start = ws

            # 3. Signal?
            if not self._want_trade(i, rng):
                continue
            self.signals += 1

            # Risk gates (mirror live RiskManager.can_open_trade ordering).
            if self.daily_pnl < -self.capital * self.daily_limit:
                self.daily_refusals += 1
                continue
            if self.weekly_pnl < -self.capital * self.weekly_limit:
                self.weekly_refusals += 1
                continue
            if len(open_pos) >= self.max_open:
                self.max_open_refusals += 1
                continue
            if self.cooldown_left > 0:
                self.cooldown_refusals += 1
                self.cooldown_left -= 1
                continue

            # 4. Randomness gate (mirror DecisionEngine.should_enter_trade).
            if rng.random() >= entry_prob:
                self.random_refusals += 1
                continue

            # 5. Size with minimum-lot protection.
            entry = closes[i] * (1 + BACKTESTING_SLIPPAGE)
            size = calculate_position_size(
                self.capital, TRADE_MANAGEMENT["position_size_risk"],
                self.stop_pct, entry, self.cfg["sym"])
            if size <= 0:
                self.size_refusals += 1
                continue

            pos = {
                "entry_time": t, "entry": entry, "size": size,
                "stop": entry * (1 - self.stop_pct),
                "tp": entry * (1 + self.tp_pct),
                "bars": 0, "trailing": False,
                "max_profit": 0.0, "max_loss": 0.0,
            }
            open_pos.append(pos)
            self.entries += 1
            self.capital -= size * self.contract * entry * BACKTESTING_COMMISSION

            # Equity mark (only meaningful with open positions).
            self.equity.append(self.capital)
            if not open_pos:
                self.equity.append(self.capital)
            _ = self.equity

        # Close anything still open at the last close.
        for pos in open_pos:
            self._close(pos, closes[-1], idx[-1], "End of research window")

        return self._stats()

    def _monitor(self, open_pos, i, closes, highs, lows, t):
        closes_i = closes[i]
        hi = highs[i]
        lo = lows[i]
        keep = []
        for pos in open_pos:
            pos["bars"] += 1
            pnl_pct = (closes_i - pos["entry"]) / pos["entry"]
            pos["max_profit"] = max(pos["max_profit"], pnl_pct)
            pos["max_loss"] = min(pos["max_loss"], pnl_pct)

            if pos["trailing"] or (
                    pnl_pct >= self.trail_active_pct):
                new_stop = closes_i * (1 - self.trail_dist_pct)
                if new_stop > pos["stop"]:
                    pos["stop"] = new_stop
                    pos["trailing"] = True

            exit_price = closes_i
            reason = None
            if lo <= pos["stop"]:
                reason = "Trailing Stop" if pos["trailing"] else "Stop Loss"
                exit_price = pos["stop"]
            elif hi >= pos["tp"]:
                reason = "Take Profit"
                exit_price = pos["tp"]
            elif pos["bars"] >= self.max_bars:
                reason = "MAX_DURATION_REACHED"
                exit_price = closes_i

            if reason is not None:
                self._close(pos, exit_price, t, reason)
            else:
                keep.append(pos)
        open_pos[:] = keep

    def _close(self, pos, exit_price, t, reason):
        exit_price = exit_price * (1 - BACKTESTING_SLIPPAGE)
        notional = pos["size"] * self.contract
        pnl = notional * (exit_price - pos["entry"])
        pnl -= notional * exit_price * BACKTESTING_COMMISSION
        pnl_pct = pnl / (pos["entry"] * notional)
        self.trades.append({
            "entry_time": pos["entry_time"], "exit_time": t,
            "pnl": pnl, "pnl_pct": pnl_pct, "reason": reason,
            "entry_price": pos["entry"], "exit_price": exit_price,
            "bars": pos["bars"], "max_profit": pos["max_profit"],
            "max_loss": pos["max_loss"],
        })
        self.capital += pnl
        self.daily_pnl += pnl
        self.weekly_pnl += pnl
        if pnl < 0:
            self.cooldown_left = self.cooldown
        else:
            self.cooldown_left = 0

    def _stats(self) -> dict:
        trades = self.trades
        total = len(trades)
        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] < 0]
        gross_w = sum(t["pnl"] for t in wins)
        gross_l = abs(sum(t["pnl"] for t in losses))
        if gross_l > 0:
            pf = gross_w / gross_l
        elif gross_w > 0:
            pf = float("inf")
        else:
            pf = 0.0
        total_ret = self.capital - self.initial_capital
        ret_pct = total_ret / self.initial_capital
        return {
            "signals": self.signals,
            "entries": self.entries,
            "executed": total,
            "size_refusals": self.size_refusals,
            "random_refusals": self.random_refusals,
            "max_open_refusals": self.max_open_refusals,
            "cooldown_refusals": self.cooldown_refusals,
            "daily_refusals": self.daily_refusals,
            "weekly_refusals": self.weekly_refusals,
            "winrate": len(wins) / total if total else 0.0,
            "profit_factor": pf if total else 0.0,
            "avg_pnl_pct": np.mean([t["pnl_pct"] for t in trades]) if total else 0.0,
            "ret_pct": ret_pct,
            "max_dd_pct": self._max_drawdown(),
            "reasons": {r: sum(1 for t in trades if t["reason"] == r)
                        for r in set(t["reason"] for t in trades)},
            "trades": trades,
            "year1": [t for t in trades if t["entry_time"].year == trades[0]["entry_time"].year] if trades else [],
            "year2": [t for t in trades if t["entry_time"].year != trades[0]["entry_time"].year] if trades else [],
        }

    def _max_drawdown(self) -> float:
        if not self.trades:
            return 0.0
        # Approximate equity using realised PnL from the initial capital.
        eq = self.initial_capital
        peak = eq
        dd = 0.0
        for t in self.trades:
            eq += t["pnl"]
            peak = max(peak, eq)
            dd = max(dd, (peak - eq) / peak if peak else 0.0)
        return dd


def per_trade_stats(trades: list) -> dict:
    if not trades:
        return {"n": 0, "winrate": 0.0, "avg_pnl_pct": 0.0, "ret_pct": 0.0}
    wins = [t for t in trades if t["pnl"] > 0]
    return {
        "n": len(trades),
        "winrate": len(wins) / len(trades),
        "avg_pnl_pct": np.mean([t["pnl_pct"] for t in trades]),
        "ret_pct": sum(t["pnl"] for t in trades),
    }


def quarterly_counts(stats: dict, sym: str, tf: str, drop: float, rule,
                     kind: str) -> list:
    """Signal counts per calendar quarter for one candidate."""
    f = explain_cache[(sym, tf)]
    m = (f["drop"] >= drop)
    if kind == "ratio":
        m &= f["vol_ratio"] >= rule
    else:
        m &= f["vol_z"] >= rule
    s = f[m].sort_index()
    return [(q, int(n)) for q, n in s["close"].resample("QE").count().items()]


explain_cache = {}


def main() -> None:
    from scripts.analyze_signal_feasibility import load_data
    data = load_data()
    for (sym, tf), df in data.items():
        data[(sym, tf)] = prepare_features(df, tf)
        explain_cache[(sym, tf)] = data[(sym, tf)]

    cands = shortlist_configs(data)
    out = []
    out.append("# Research Candidate Backtests (Relaxed Bad-Luck Signals, Real Data)\n")
    out.append("## Methodology\n")
    out.append("- Entry mask = relaxed candidate only (drop AND volume screen; "
               "the same-bar reversal-pattern + ATR-spike stack of the production "
               "detector is NOT applied here - see the feasibility report for why "
               "it fires zero times on real data).\n")
    out.append(f"- Trade management mirrors production: stop {TRADE_MANAGEMENT['stop_loss_pct']:.2%}, "
               f"TP {TRADE_MANAGEMENT['take_profit_pct']:.2%}, trailing after "
               f"{TRADE_MANAGEMENT['trailing_activation_pct']:.2%} (distance "
               f"{TRADE_MANAGEMENT['trailing_distance_pct']:.2%}), max "
               f"{TRADE_MANAGEMENT['max_duration_candles']} bars, commission "
               f"{BACKTESTING_COMMISSION:.2%} per side, slippage "
               f"{BACKTESTING_SLIPPAGE:.2%}.\n")
    out.append(f"- Risk limits enabled (live mirror): daily {RISK_MANAGEMENT['max_daily_loss']:.0%}, "
               f"weekly {RISK_MANAGEMENT['max_weekly_loss']:.0%}, cooldown "
               f"{RISK_MANAGEMENT['cooldown_after_loss']} trades after a loss, max "
               f"{RISK_MANAGEMENT['max_open_trades']} open positions. Minimum-lot "
               "sizing uses calculate_position_size.\n")
    out.append(f"- Randomness gate: seeded replica of the DecisionEngine rule "
               f"(random < {RANDOM_DECISION['entry_probability']}). Default capital "
               f"{BACKTESTING_INITIAL_CAPITAL} for the equity run; refusals also "
               "reported for other capital scenarios.\n")

    rows = []
    for n, c in enumerate(cands):
        sim = CandidateSim(data[(c["sym"], c["tf"])], c, BACKTESTING_INITIAL_CAPITAL)
        st = sim.run(SEED_BASE + n, RANDOM_DECISION["entry_probability"])
        y1 = per_trade_stats(st["year1"])
        y2 = per_trade_stats(st["year2"])
        sc = {k: v for k, v in SUCCESS_CRITERIA.items()}
        crit = (st["winrate"] >= sc["min_win_rate"] and
                st["profit_factor"] >= sc["min_profit_factor"] and
                st["max_dd_pct"] <= sc["max_drawdown"] and
                st["entries"] >= sc["min_trades"])
        rows.append((c, st, y1, y2, crit))
        print(f"sim done: {c['sym']} {c['tf']} drop={c['drop']} "
              f"{c['kind']}{c['rule']} signals={st['signals']} "
              f"traded={st['executed']} ret={st['ret_pct']:.2%}", flush=True)

    out.append("\n## Summary (long entries, capital "
               f"{BACKTESTING_INITIAL_CAPITAL}, risk limits + randomness on)\n")
    out.append("| # | Sym | TF | drop | screen | signals | random-skip | "
               "size-refuse | entries | traded | win% | PF | avg/trade | "
               "ret% | maxDD% | success |\n")
    out.append("|---|-----|----|------|--------|---------|-------------|"
               "------------|---------|--------|------|----|-----------|"
               "------|--------|---------|\n")
    for n, (c, st, _, _, crit) in enumerate(rows):
        out.append(
            f"| {n+1} | {c['sym']} | {c['tf']} | {c['drop']:.4f} | "
            f"{c['kind']}{c['rule']:.2f} | {st['signals']} | "
            f"{st['random_refusals']} | {st['size_refusals']} | "
            f"{st['entries']} | {st['executed']} | {st['winrate']*100:.1f}% | "
            f"{st['profit_factor']:.2f} | {st['avg_pnl_pct']*100:.3f}% | "
            f"{st['ret_pct']*100:.2f}% | {st['max_dd_pct']*100:.2f}% | "
            f"{'YES' if crit else 'no'} |\n"
        )

    out.append("\n## Risk-gate refusals detail (capital "
               f"{BACKTESTING_INITIAL_CAPITAL})\n")
    out.append("| # | Sym | TF | drop | screen | signals | max-open | "
               "cooldown | daily-loss | weekly-loss |\n")
    out.append("|---|-----|----|------|--------|---------|----------|"
               "----------|------------|-------------|\n")
    for n, (c, st, _, _, _) in enumerate(rows):
        out.append(
            f"| {n+1} | {c['sym']} | {c['tf']} | {c['drop']:.4f} | "
            f"{c['kind']}{c['rule']:.2f} | {st['signals']} | "
            f"{st['max_open_refusals']} | {st['cooldown_refusals']} | "
            f"{st['daily_refusals']} | {st['weekly_refusals']} |\n"
        )

    out.append("\n## Minimum-lot sizing refusals by capital scenario "
               "(same signal pools, always-on seeds)\n")
    out.append("Rate = would-be trades refused because the 2% risk budget "
               "cannot cover one 0.01 lot at the signal price.\n")
    out.append("| # | Sym | TF | drop | screen | " +
               " | ".join(f"{k}" for k in CAPITAL_SCENARIOS) + " |\n")
    out.append("|---|-----|----|------|--------|" + "-----|" * len(CAPITAL_SCENARIOS) + "\n")
    for n, (c, st, _, _, _) in enumerate(rows):
        cells = []
        f = data[(c["sym"], c["tf"])]
        m = (f["drop"] >= c["drop"])
        m &= f["vol_ratio"] >= c["rule"] if c["kind"] == "ratio" else f["vol_z"] >= c["rule"]
        sig_prices = f.loc[m, "close"].values
        for k in CAPITAL_SCENARIOS:
            nref = 0
            for px in sig_prices:
                sz = calculate_position_size(
                    k, TRADE_MANAGEMENT["position_size_risk"],
                    TRADE_MANAGEMENT["stop_loss_pct"],
                    px * (1 + BACKTESTING_SLIPPAGE), c["sym"])
                if sz <= 0:
                    nref += 1
            cells.append(f"{nref}/{len(sig_prices)} ({nref/max(1,len(sig_prices))*100:.0f}%)")
        out.append(f"| {n+1} | {c['sym']} | {c['tf']} | {c['drop']:.4f} | "
                   f"{c['kind']}{c['rule']:.2f} | " + " | ".join(cells) + " |\n")

    out.append("\n## Year 1 vs Year 2 (per-trade realised statistics)\n")
    out.append("The first calendar year in the sample is 2024-2025; the "
               "second is 2025-2026. Trade-level stats are shown because the "
               "sample is dominated by year-2 events for some assets.\n")
    out.append("| # | Sym | TF | drop | screen | Y1 n | Y1 win% | Y1 avg% | "
               "Y2 n | Y2 win% | Y2 avg% | Y1+Y2 ret$\n")
    out.append("|---|-----|----|------|--------|------|---------|---------|"
               "------|---------|---------|----------|\n")
    for n, (c, _, y1, y2, _) in enumerate(rows):
        out.append(
            f"| {n+1} | {c['sym']} | {c['tf']} | {c['drop']:.4f} | "
            f"{c['kind']}{c['rule']:.2f} | {y1['n']} | {y1['winrate']*100:.1f}% | "
            f"{y1['avg_pnl_pct']*100:.3f}% | {y2['n']} | {y2['winrate']*100:.1f}% | "
            f"{y2['avg_pnl_pct']*100:.3f}% | {y1['ret_pct']+y2['ret_pct']:.0f} |\n"
        )

    out.append("\n## Quarterly signal frequency (relaxed candidates)\n")
    out.append("| # | Sym | TF | drop | screen | " +
               " | ".join(f"Q{i+1}" for i in range(8)) + " |\n")
    out.append("|---|-----|----|------|--------|" + "-----|" * 8 + "\n")
    for n, (c, st, _, _, _) in enumerate(rows):
        q = quarterly_counts(st, c["sym"], c["tf"], c["drop"], c["rule"], c["kind"])
        cells = [f"{cnt}" for _, cnt in q[:8]]
        while len(cells) < 8:
            cells.append("0")
        out.append(f"| {n+1} | {c['sym']} | {c['tf']} | {c['drop']:.4f} | "
                   f"{c['kind']}{c['rule']:.2f} | " + " | ".join(cells[:8]) + " |\n")

    out.append("\n## Exit reason distribution (top candidate per timeframe)\n")
    seen_tf = {}
    for n, (c, st, _, _, _) in enumerate(rows):
        if c["tf"] not in seen_tf and st["executed"] > 0:
            seen_tf[c["tf"]] = (n, c, st)
    for tf in ["M15", "M30", "H1"]:
        if tf not in seen_tf:
            continue
        n, c, st = seen_tf[tf]
        out.append(f"\n### {c['sym']} {tf} drop={c['drop']} {c['kind']}{c['rule']} "
                   f"({st['executed']} trades)\n")
        out.append("| reason | count | share | avg pnl% |\n")
        out.append("|--------|-------|-------|----------|\n")
        for r in sorted(st["reasons"], key=lambda r: -st["reasons"][r]):
            rt = [t for t in st["trades"] if t["reason"] == r]
            out.append(f"| {r} | {len(rt)} | {len(rt)/len(st['trades'])*100:.1f}% | "
                       f"{np.mean([t['pnl_pct'] for t in rt])*100:.3f}% |\n")

    dst = Path("reports/research_candidate_backtests.md")
    dst.write_text("".join(out), encoding="utf-8")
    print(f"report written: {dst.resolve()}")


if __name__ == "__main__":
    main()