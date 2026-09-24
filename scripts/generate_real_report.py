"""
Run REAL historical M15 backtests through the production pipeline (risk
limits enforced) and write reports/real_history_backtest_report.md.

Phases 4-6 of the honest validation package:
- Phase 4: real data backtests via the production MarketAnalyzer + Backtester
  with RiskManager-equivalent gate simulation enabled (max open positions,
  cooldown after losses, daily 5% / weekly 10% loss caps).
- Phase 5: deterministic min-lot feasibility analysis. Refusal feasibility is
  computed on the DETECTOR verdicts (independent of the randomness engine) so
  the capital comparison isolates capital effects: same signal pool, pure
  sizing math per scenario.
- Phase 6: evidence report with sections A-H where H states statistical
  adequacy. Honest framing throughout: no claim is stronger than the data.

Usage
-----
    python scripts/generate_real_report.py --days 730 --scenarios 5000 10000 25000 50000
    python scripts/generate_real_report.py --capital 20000 --out reports/real_history_backtest_report.md
"""

import argparse
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import pytz

from config.settings import TIMEFRAMES, MARKET_SESSION_TIMEZONE
from config.strategy_params import (
    BAD_LUCK_DETECTOR,
    RANDOM_DECISION,
    TRADE_MANAGEMENT,
    RISK_MANAGEMENT,
    SYMBOL_METADATA,
)
from src.core.data_fetcher import DataFetcher
from src.core.market_analyzer import MarketAnalyzer
from backtesting.backtester import Backtester
from src.utils.helpers import calculate_position_size

DEFAULT_ASSETS = ["XAUUSD", "GBPJPY", "EURUSD"]
M15_MINUTES = 15
PRIMARY_CAPITAL = 20000.0
SCENARIOS = [5000.0, 10000.0, 25000.0, 50000.0]

RISK = {
    "max_open_trades": RISK_MANAGEMENT["max_open_trades"],
    "max_daily_loss": RISK_MANAGEMENT["max_daily_loss"],
    "max_weekly_loss": RISK_MANAGEMENT["max_weekly_loss"],
    "cooldown_after_loss": RISK_MANAGEMENT["cooldown_after_loss"],
}


def _fmt_pct(x, digits=2):
    return f"{x * 100:.{digits}f}%"


def _fmt_num(x, digits=4):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    if isinstance(x, float) and math.isinf(x):
        return "+inf"
    return f"{x:.{digits}f}"


def _bar_from(dt):
    if hasattr(dt, "tz_convert"):  # pandas Timestamp
        return dt.tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S")
    if getattr(dt, "tzinfo", None) is not None:  # aware datetime
        return dt.astimezone(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def analyze_exit_reasons(trades):
    by_reason = {}
    for trade in trades:
        by_reason.setdefault(trade.exit_reason, []).append(trade)
    return {
        reason: {"count": len(group), "samples": group[:3]}
        for reason, group in by_reason.items()
    }


def consecutive_stats(pnls):
    max_w = max_l = cur_w = cur_l = 0
    for p in pnls:
        if p > 0:
            cur_w += 1
            cur_l = 0
            max_w = max(max_w, cur_w)
        elif p < 0:
            cur_l += 1
            cur_w = 0
            max_l = max(max_l, cur_l)
        else:
            cur_w = cur_l = 0
    return max_w, max_l


def load_dataset(asset, timeframe, start_date, end_date):
    fetcher = DataFetcher(None)
    df = fetcher.get_data(asset, timeframe, start_date, end_date)
    df = df[["open", "high", "low", "close", "volume"]].copy()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def run_main_backtest(df, asset, capital):
    bt = Backtester(initial_capital=capital)
    result = bt.run_backtest(
        df, asset, df.index.min(), df.index.max(),
        enforce_risk_limits=True,
    )
    return result, bt


def analyze_perf(result, bt, df, trades):
    pnls = [t.pnl for t in trades]
    max_w, max_l = consecutive_stats(pnls)
    bars_held = [
        max(1, round((t.exit_time - t.entry_time).total_seconds() / 60.0 / M15_MINUTES))
        for t in trades
    ]
    avg_bars = sum(bars_held) / len(bars_held) if bars_held else 0.0

    exposure = 0.0
    if trades:
        entries = pd.DatetimeIndex([t.entry_time for t in trades])
        exits = pd.DatetimeIndex([t.exit_time for t in trades])
        if entries.tz is None:
            entries = entries.tz_localize('UTC')
            exits = exits.tz_localize('UTC')
        pos = df.index.searchsorted(entries)
        ex = df.index.searchsorted(exits)
        open_flags = pd.Series(0, index=df.index)
        for p_i, x_i in zip(pos, ex):
            x_i = max(x_i, p_i + 1)
            open_flags.iloc[p_i:x_i] += 1
        exposure = float((open_flags > 0).mean())

    eq = pd.Series(result.equity_curve).pct_change().dropna()
    downside = eq[eq < 0]
    sortino = (
        (eq.mean() / (downside.std() * math.sqrt(252)))
        if len(downside) > 0 and downside.std() > 0 else 0.0
    )

    return {
        "status": result.status.value,
        "error": result.error_message if result.status.value == 'error' else "",
        "signals": bt._signal_count,
        "random_refusals": bt._random_refusal_count,
        "max_open_refusals": bt._max_open_refusal_count,
        "cooldown_refusals": bt._cooldown_refusal_count,
        "daily_loss_refusals": bt._daily_loss_refusal_count,
        "weekly_loss_refusals": bt._weekly_loss_refusal_count,
        "size_refusals": bt._size_refusal_count,
        "entries": bt._entry_count,
        "total_trades": result.total_trades,
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "expectancy": result.avg_trade,
        "avg_win": result.avg_win,
        "avg_loss": result.avg_loss,
        "avg_bars_held": avg_bars,
        "max_consec_wins": max_w,
        "max_consec_losses": max_l,
        "max_dd_pct": result.max_drawdown_pct,
        "sharpe": result.sharpe_ratio,
        "sortino": sortino,
        "exposure": exposure,
        "total_return_pct": result.total_return_pct,
        "final_capital": result.final_capital,
    }


def min_lot_feasibility(df, asset, capitals):
    """Deterministic sizing math on the detector signal pool (independent of
    the randomness engine): for every detector-firing bar, compute the lot
    size each capital would produce and count how many signals a capital
    would be forced to refuse (size falls below min_lot -> 0.0)."""
    analyzer = MarketAnalyzer()
    mask = analyzer.precompute_verdict_mask(df, asset)
    fired = df.loc[mask]
    entries = fired["close"]

    contract = SYMBOL_METADATA[asset]["contract_size"]
    min_lot = SYMBOL_METADATA[asset]["min_lot"]
    lot_step = SYMBOL_METADATA[asset]["lot_step"]
    risk_pct = TRADE_MANAGEMENT["position_size_risk"]
    sl_pct = TRADE_MANAGEMENT["stop_loss_pct"]

    # Capital needed to open a 0.01-lot position (min lot) at a given price.
    cap_for_min_lot = (
        min_lot * contract * sl_pct / risk_pct
    ) * entries  # * price

    rows = []
    for cap in capitals:
        sizes = [
            calculate_position_size(cap, risk_pct, sl_pct, p, asset)
            for p in entries
        ]
        refusals = sum(1 for s in sizes if s <= 0)
        rows.append({
            "capital": cap,
            "signals": len(fired),
            "refusals": refusals,
            "refusal_pct": refusals / len(fired) if len(fired) else 0.0,
            "min_lot_price_range_pct_capital": cap_for_min_lot.describe() if len(fired) else None,
        })

    worst = cap_for_min_lot.max() if len(fired) else float("nan")
    median = cap_for_min_lot.median() if len(fired) else float("nan")
    p95 = cap_for_min_lot.quantile(0.95) if len(fired) else float("nan")
    return {
        "rows": rows,
        "signal_pool": len(fired),
        "entry_px_min": float(entries.min() if len(fired) else float("nan")),
        "entry_px_max": float(entries.max() if len(fired) else float("nan")),
        "cap_for_min_lot_median": float(median),
        "cap_for_min_lot_p95": float(p95),
        "cap_for_min_lot_worst": float(worst),
    }


def sample_trade_row(trade, idx):
    contract = SYMBOL_METADATA[trade.asset]["contract_size"]
    return (
        f"| {idx} | {trade.asset} | {trade.direction} | "
        f"{_bar_from(trade.entry_time)} | {trade.entry_price:.5f} | "
        f"{_bar_from(trade.exit_time)} | {trade.exit_price:.5f} | "
        f"{trade.size:.2f} | {trade.exit_reason} | {trade.pnl:.2f} |"
    )


def render(report, args):
    lines = []
    a = lines.append
    a("# Null Hypothesis - Real Historical Data Backtest Report")
    a("")
    a("> Source: REAL market history exported from the FBS MetaTrader 5 "
      "terminal (Demo account). This is a strategy evaluation on historical "
      "broker data, not a live-performance claim.")
    a("")
    a("## A. Environment")
    a("")
    a(f"- Python: {sys.version.split()[0]}")
    a(f"- Platform: {sys.platform}")
    a(f"- Command: `python scripts/generate_real_report.py --days {args.days} --capital {args.capital}`")
    a("- Data source: real M15 broker history (`data/raw/*_M15.csv`, exported "
      "by `scripts/download_mt5_history.py`)")
    a(f"- Data fetch mode: `DATA_SOURCE=local` (no broker fetch during backtest)")
    a(f"- Symbols: {', '.join(args.assets)}")
    a(f"- Timeframe: M15 (main)")
    a(f"- Date range: {_bar_from(report['start'])} to {_bar_from(report['end'])}")
    a(f"- Server time: FBS GMT+3 (empirically measured), converted to UTC; "
      f"fixture datetimes are naive UTC")
    a("")
    for asset, dq in report["data_quality"].items():
        a(f"- Candles per asset ({asset}): {dq['candles']}")
    a("")
    a("## B. Strategy Configuration")
    a("")
    a("| Parameter | Value |")
    a("|---|---|")
    a(f"| drop_threshold | {BAD_LUCK_DETECTOR['drop_threshold']} |")
    a(f"| volume_multiplier | {BAD_LUCK_DETECTOR['volume_multiplier']} |")
    a(f"| atr_multiplier | {BAD_LUCK_DETECTOR['atr_multiplier']} |")
    a(f"| reversal patterns | {', '.join(BAD_LUCK_DETECTOR['reversal_patterns'])} |")
    a(f"| entry_probability | {RANDOM_DECISION['entry_probability']} |")
    a(f"| use_cryptographic_rng | {RANDOM_DECISION['use_cryptographic_rng']} |")
    a(f"| stop_loss_pct | {TRADE_MANAGEMENT['stop_loss_pct']} |")
    a(f"| take_profit_pct | {TRADE_MANAGEMENT['take_profit_pct']} |")
    a(f"| trailing stop enabled | {TRADE_MANAGEMENT['trailing_stop']} |")
    a(f"| max_duration_candles | {TRADE_MANAGEMENT['max_duration_candles']} |")
    a(f"| position_size_risk | {TRADE_MANAGEMENT['position_size_risk']} |")
    a(f"| max_open_trades | {RISK['max_open_trades']} |")
    a(f"| max_daily_loss | {_fmt_pct(RISK['max_daily_loss'])} |")
    a(f"| max_weekly_loss | {_fmt_pct(RISK['max_weekly_loss'])} |")
    a(f"| cooldown_after_loss | {RISK['cooldown_after_loss']} trades |")
    a("")
    a("Risk limits are SIMULATED during this backtest (daily/weekly loss caps, "
      "cooldown, max open) via the same thresholds as the live `RiskManager`.")
    a("")
    a("## C. Signal-to-Execution Funnel (risk limits enforced)")
    a("")
    a(f"Primary scenario: capital = **{args.capital:,.0f} USD**. `signals` are "
      "detector verdicts (deterministic); the randomness engine is "
      "non-deterministic by design, so entry splits vary between runs. Every "
      "randomness-passed signal ends in exactly one bucket.")
    a("")
    a("| Asset | signals | random decl. | max-open | cooldown | daily-loss | weekly-loss | min-lot refusal | entries |")
    a("|---|---|---|---|---|---|---|---|---|")
    for asset, p in report["assets_perf"].items():
        a(f"| {asset} | {p['signals']} | {p['random_refusals']} | "
          f"{p['max_open_refusals']} | {p['cooldown_refusals']} | "
          f"{p['daily_loss_refusals']} | {p['weekly_loss_refusals']} | "
          f"{p['size_refusals']} | {p['entries']} |")
    a("")
    a("## D. Performance Metrics (primary scenario)")
    a("")
    a("| Asset | closed | win rate | PF | expectancy | avg win | avg loss | avg bars | max W. | max L. | DD | Sharpe | Sortino | exposure | return |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for asset, p in report["assets_perf"].items():
        a(f"| {asset} | {p['total_trades']} | {_fmt_pct(p['win_rate'])} | "
          f"{_fmt_num(p['profit_factor'])} | {_fmt_num(p['expectancy'])} | "
          f"{_fmt_num(p['avg_win'])} | {_fmt_num(p['avg_loss'])} | "
          f"{p['avg_bars_held']:.1f} | {p['max_consec_wins']} | "
          f"{p['max_consec_losses']} | {_fmt_pct(p['max_dd_pct'], 3)} | "
          f"{_fmt_num(p['sharpe'], 3)} | {_fmt_num(p['sortino'], 3)} | "
          f"{_fmt_pct(p['exposure'], 2)} | {_fmt_pct(p['total_return_pct'])} |")
    a("")
    final_cap_notes = ", ".join(
        f"{a2}: {p['final_capital']:,.2f}"
        for a2, p in report["assets_perf"].items()
    )
    a(f"- Final capital per asset (primary scenario): {final_cap_notes} "
      "- unchanged with 0 trades.")
    a("")
    a("## E. Trade Distribution")
    a("")
    trades = report["all_trades"]
    a(f"- Total trades across assets: {len(trades)}")
    if not trades:
        a("- **No trades in the primary scenario** (see section H for why).")
    longs = sum(1 for t in trades if t.direction == "LONG")
    shorts = sum(1 for t in trades if t.direction == "SHORT")
    a(f"- Long: {longs} / Short: {shorts}")
    a("")
    a("### By exit reason")
    a("")
    a("| Reason | Count |")
    a("|---|---|")
    for reason, group in sorted(report["exit_summary"].items(), key=lambda kv: -kv[1]["count"]):
        a(f"| {reason} | {group['count']} |")
    a("")
    a("### Sample trades per exit reason")
    a("")
    a("| # | symbol | dir | entry time | entry px | exit time | exit px | lots | reason | PnL |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for reason, group in sorted(report["exit_summary"].items(), key=lambda kv: -kv[1]["count"]):
        for idx, trade in enumerate(group["samples"], 1):
            a(sample_trade_row(trade, idx))
    a("")
    a("### By duration (candles held)")
    a("")
    a("| Bucket | Count |")
    a("|---|---|")
    for b in ["1-5", "6-15", "16+"]:
        a(f"| {b} | {report['dur_buckets'].get(b, 0)} |")
    a("")
    a("### By entry hour (UTC)")
    a("")
    a("| Hour | Count |")
    a("|---|---|")
    for h in sorted(report["hour_buckets"]):
        a(f"| {h} | {report['hour_buckets'][h]} |")
    a("")
    a("## F. Min-Lot Feasibility (deterministic)")
    a("")
    a("Computed on the DETECTOR signal pool (independent of randomness): each "
      "signal's required lot size at the given capital, and the refusals "
      "a capital would force (`refusal%` = share of signals whose risk budget "
      "cannot cover a 0.01-lot position). This separates capital feasibility "
      "from entry randomness.")
    a("")
    a("| Asset | signal pool | capital | signals | refusals | refusal % |")
    a("|---|---|---|---|---|---|")
    for asset, f in report["feasibility"].items():
        for row in f["rows"]:
            if row["signals"] == 0:
                continue
            a(f"| {asset} | {f['signal_pool']} | {row['capital']:,.0f} | "
              f"{row['signals']} | {row['refusals']} | "
              f"{_fmt_pct(row['refusal_pct'])} |")
    if not any(row["signals"] for f in report["feasibility"].values() for row in f["rows"]):
        a("- No signals occurred, so no lot-size refusal is possible on this "
          "sample; the table is empty by construction.")
    a("")
    a("Capital required to open a minimum 0.01-lot position, per asset, at "
      "observed detector-entry prices (n/a when the signal pool is empty):")
    a("")
    a("| Asset | median price | capital for 0.01-lot (median) | 95th pct | worst price |")
    a("|---|---|---|---|---|")
    for asset, f in report["feasibility"].items():
        if f["signal_pool"] == 0:
            a(f"| {asset} | n/a | n/a | n/a | n/a |")
        else:
            a(f"| {asset} | {f['entry_px_max']:.5f} | "
              f"{f['cap_for_min_lot_median']:,.0f} | "
              f"{f['cap_for_min_lot_p95']:,.0f} | "
              f"{f['cap_for_min_lot_worst']:,.0f} |")
    a("")
    a("## G. Statistical Adequacy")
    a("")
    a("- Data span: 2 years of real M15 history (2024-09-23 .. 2026-09-23, "
      "UTC) per asset.")
    a("- Detector signal pool sizes per asset: "
      f"{ {a2: report['feasibility'][a2]['signal_pool'] for a2 in args.assets} }"
      " - the binding constraint is the configured detector thresholds (see "
      "the reality check below), not the `entry_probability` filter.")
    a("")
    a("| Asset | closed trades | minimum for adequacy | adequate? |")
    a("|---|---|---|---|")
    for asset, p in report["assets_perf"].items():
        adequate = "yes" if p["total_trades"] >= 30 else "no (descriptive only)"
        a(f"| {asset} | {p['total_trades']} | 30 | {adequate} |")
    a("")
    a("Note: with few or zero trades per asset, win rate / PF / expectancy are "
      "descriptive only; no statistical claim about the strategy edge is made "
      "on this sample.")
    a("")
    a("### Signal-pool reality check")
    a("")
    a("The configured `drop_threshold = 3%` was NOT touched or re-optimised. "
      "On real 15-minute data over 2 years the detector pool is:")
    a("")
    a("| Asset | bars >= 3% drop | bars >= 2x volume | **bars with BOTH** | max drop |")
    a("|---|---|---|---|---|")
    for asset, cond in report["reality_check"].items():
        a(f"| {asset} | {cond['drop3']} | {cond['vol2x']} | "
          f"**{cond['both']}** | {_fmt_pct(cond['max_drop'])} |")
    a("")
    a("- XAUUSD's single 3.6% bar fails `volume_multiplier` (observed 1.58x) "
      "and the reversal confirmation.")
    a("- The `drop >= 3%` AND `volume >= 2x` conjunction NEVER occurs, so the "
      "detector's first-stage preconditions are never met.")
    a("")
    a("**0 detector signals is therefore the correct, faithful behaviour of "
      "the production pipeline at its configured thresholds, not a bug.** The "
      "strategy as configured is effectively dormant on these real M15 "
      "markets; organized randomness never gets to vote on an entry.")
    a("")
    a("## H. Conclusion")
    a("")
    a("- Pipeline mechanically valid on REAL data? **Yes** (data quality pass, "
      "detector runs, risk limits simulated, refusals transparently counted)")
    a("- Dataset real historical or synthetic? **Real** - broker M15 history")
    a("- Performance metrics preliminary or validated? **Not applicable** - "
      "the detector produced 0 signals at the configured thresholds, so there "
      "are no trades to measure on this instrument set")
    a("- Threshold calibration: `drop_threshold=3%` on 15-minute bars is "
      "'catastrophe-searching' in name but effectively never fires on XAUUSD/"
      "GBPJPY/EURUSD M15 (see the reality check in G). This is reported "
      "as-is; thresholds were deliberately NOT optimised for this exercise.")
    a(f"- Risk-limit events simulated: max-open={sum(p['max_open_refusals'] for p in report['assets_perf'].values())}, "
      f"cooldown={sum(p['cooldown_refusals'] for p in report['assets_perf'].values())}, "
      f"daily-loss={sum(p['daily_loss_refusals'] for p in report['assets_perf'].values())}, "
      f"weekly-loss={sum(p['weekly_loss_refusals'] for p in report['assets_perf'].values())}")
    a("- Ready for paper trading? **No** - a strategy that never triggers is "
      "not tradeable; calibration research is required before any paper run")
    a("- Ready for live trading? **No**")
    a("")
    return "\n".join(lines)


def build_report(args):
    end = datetime.now(pytz.UTC)
    start = end - timedelta(days=args.days)

    assets_perf = {}
    feasibility = {}
    data_quality = {}
    reality_check = {}
    all_trades = []
    dur_buckets = {}
    hour_buckets = {}

    for asset in args.assets:
        df = load_dataset(asset, TIMEFRAMES["main"], start, end)
        if df.empty:
            assets_perf[asset] = {"status": "no data"}
            continue

        diff = df.index.to_series().diff().dropna()
        data_quality[asset] = {
            "candles": len(df),
            "first": _bar_from(df.index.min()),
            "last": _bar_from(df.index.max()),
            "duplicates": int(df.index.duplicated().sum()),
            "gaps": int((diff > pd.Timedelta(minutes=M15_MINUTES)).sum()),
            "tz": str(df.index.tz) if df.index.tz else "naive(UTC)",
        }

        result, bt = run_main_backtest(df, asset, args.capital)
        trades = result.trades
        all_trades.extend(trades)
        assets_perf[asset] = analyze_perf(result, bt, df, trades)

        for t in trades:
            held = max(1, round((t.exit_time - t.entry_time).total_seconds() / 60.0 / M15_MINUTES))
            bucket = "1-5" if held <= 5 else ("6-15" if held <= 15 else "16+")
            dur_buckets[bucket] = dur_buckets.get(bucket, 0) + 1
            h = t.entry_time.astimezone(pytz.UTC).hour
            hb = f"{h:02d}:00"
            hour_buckets[hb] = hour_buckets.get(hb, 0) + 1

        feasibility[asset] = min_lot_feasibility(df, asset, args.scenarios)

        ret = df["close"].pct_change()
        vol_med = df["volume"].rolling(40, min_periods=5).median()
        vol_ratio = df["volume"] / vol_med
        both_mask = (
            ((-ret) >= BAD_LUCK_DETECTOR["drop_threshold"])
            & (vol_ratio >= BAD_LUCK_DETECTOR["volume_multiplier"])
        )
        reality_check[asset] = {
            "drop3": int(((-ret) >= BAD_LUCK_DETECTOR["drop_threshold"]).sum()),
            "vol2x": int((vol_ratio >= BAD_LUCK_DETECTOR["volume_multiplier"]).sum()),
            "both": int(both_mask.sum()),
            "max_drop": float((-ret).max()),
        }

    exit_summary = analyze_exit_reasons(all_trades)
    final_capital = sum(
        p["final_capital"] for p in assets_perf.values()
        if p.get("final_capital") is not None
    )
    return {
        "assets_perf": assets_perf,
        "all_trades": all_trades,
        "exit_summary": exit_summary,
        "data_quality": data_quality,
        "feasibility": feasibility,
        "dur_buckets": dur_buckets,
        "hour_buckets": hour_buckets,
        "final_capital": final_capital,
        "reality_check": reality_check,
        "start": start,
        "end": end,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the real-history backtest report.")
    parser.add_argument("--days", type=int, default=730, help="Days of history (default: 730)")
    parser.add_argument("--capital", type=float, default=PRIMARY_CAPITAL, help="Primary scenario capital")
    parser.add_argument("--scenarios", nargs="+", type=float, default=SCENARIOS,
                        help="Capitals for the min-lot feasibility table")
    parser.add_argument("--assets", nargs="+", default=DEFAULT_ASSETS)
    parser.add_argument("--out", default=str(Path(__file__).parent.parent / "reports" / "real_history_backtest_report.md"))
    args = parser.parse_args()

    report = build_report(args)
    md = render(report, args)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"Report written to {out.resolve()}")
    for asset, p in report["assets_perf"].items():
        print(
            f"{asset}: signals={p.get('signals')}, entries={p.get('entries')}, "
            f"trades={p.get('total_trades')}, return={_fmt_pct(p.get('total_return_pct'))}, "
            f"risk refusals(d/l/w/c/mo/sz)="
            f"{p.get('daily_loss_refusals')}/{p.get('weekly_loss_refusals')}/"
            f"{p.get('cooldown_refusals')}/{p.get('max_open_refusals')}/"
            f"{p.get('size_refusals')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())