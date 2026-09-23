"""
Analyze signal feasibility and threshold calibration on REAL historical data.

This script performs the Phase A / Phase B feasibility research only. It never
touches production configuration and never changes trading behaviour. It reads
the real CSVs exported by scripts/download_mt5_history.py and writes:

    reports/signal_feasibility_report.md

Sections produced:
  A1  Negative-return distributions per symbol x timeframe.
  A2  Volume behaviour: ratio-to-20-bar-average, z-score, and trailing
      percentile screens, plus session activity.
  A3  ATR behaviour: ATR as % of price and "drop as a multiple of ATR".
  A4  Joint drop x volume occurrence matrices, including dynamic
      trailing-percentile drop thresholds with a floor (no lookahead).
  A5  Reversal-pattern co-occurrence and the full production detector
      condition stack at relaxed candidate thresholds.
  B1  Forward-return edge for a shortlist of candidate configs compared
      against an identically-sized random baseline.

Evaluation rules honoured:
  - Trailing windows only; no forward-looking information anywhere.
  - The floor of the dynamic threshold prevents absurd thresholds in calm
    markets and is documented per timeframe.
  - A config is only promoted to the shortlist if it produces a meaningful
    number of signals over the full two-year window and per calendar year.
  - No synthetic data is used as evidence; everything here is real data.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.strategy_params import BAD_LUCK_DETECTOR  # noqa: E402
from src.utils.indicators import calculate_atr, is_reversal_pattern  # noqa: E402

BAR_MINUTES = {"M5": 5, "M15": 15, "M30": 30, "H1": 60}

# Per-timeframe drop candidate grids (factor of 2 away from the production
# 0.03 threshold; all far more frequent in expectation).
DROP_CANDIDATES = {
    "M5": [0.0015, 0.002, 0.003, 0.004, 0.005],
    "M15": [0.002, 0.003, 0.005, 0.008, 0.010],
    "M30": [0.0025, 0.004, 0.0065, 0.009, 0.012],
    "H1": [0.003, 0.005, 0.008, 0.010, 0.015],
}

# Absolute floor under the dynamic threshold in bar-move terms. A bar move of
# half the typical daily range on EURUSD (the most liquid / least volatile of
# the three) is still firm noise, so the floor sits at roughly one third of a
# "typical" bar for the smallest-scale instruments. Same floor for every
# symbol so we do not overfit per-symbol floors.
DYNAMIC_FLOOR = {"M5": 0.0005, "M15": 0.001, "M30": 0.0015, "H1": 0.002}

# Trailing windows for the dynamic percentile threshold, in bars
# (1 week / 2 weeks / ~1 month with MT5's ~4.3-week month).
ROLLING_WINDOWS = {"M5": (1920, 3840, 8256),
                   "M15": (480, 960, 2064),
                   "M30": (240, 480, 1032),
                   "H1": (120, 240, 516)}

VOLUME_RATIOS = [1.5, 2.0, 2.5, 3.0]
VOLUME_Z = [2.0, 3.0]
VOLUME_PCT = [0.95, 0.98, 0.99]
VOL_ZS_WINDOW = 100
VOL_PCT_WINDOW = 100

ATR_MULTIPLES = [2.0, 3.0, 4.0, 5.0]
FWD_HORIZONS = [15, 30, 60, 120]
FWD_DRAWS = 5
RANDOM_SEED = 42

# Symbols actually exported from the real terminal.
SYMBOLS = ["XAUUSD", "GBPJPY", "EURUSD"]
# Timeframes with full two-year real history on the FBS demo terminal.
STUDY_TFS = ["M15", "M30", "H1"]

SESSION_HOURS = {"Asia": (0, 8), "London": (7, 16), "New York": (12, 21)}


def read_real_csv(path: Path) -> pd.DataFrame:
    """Read a real exported CSV exactly like scripts/validate_real_data.py."""
    with path.open(encoding="utf-8") as fh:
        for _ in range(30):
            line = fh.readline()
            if not line.startswith("#"):
                break
    df = pd.read_csv(path, comment="#", index_col=0, parse_dates=True)
    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC")
    else:
        df.index = df.index.tz_localize("UTC")
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def load_data() -> dict:
    """Load real data for every symbol and study timeframe."""
    data = {}
    base = Path(__file__).parent.parent / "data" / "raw"
    for sym in SYMBOLS:
        for tf in STUDY_TFS:
            path = base / f"{sym}_{tf}.csv"
            if not path.exists():
                raise FileNotFoundError(f"Missing real data: {path}")
            df = read_real_csv(path)
            data[(sym, tf)] = df
    return data


def prepare_features(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Build the trailing-only feature columns needed by the analysis."""
    f = pd.DataFrame(index=df.index)
    f["open"] = df["open"]
    f["close"] = df["close"]
    f["high"] = df["high"]
    f["low"] = df["low"]
    f["volume"] = df["volume"]

    # Price drop (positive when the bar closed lower).
    prev_close = df["close"].shift(1)
    f["drop"] = (prev_close - df["close"]) / prev_close

    # Volume ratio vs mean of the previous volume_period bars (detector
    # formula: excludes the current bar from its own baseline).
    vp = BAD_LUCK_DETECTOR["volume_period"]
    vol_avg = df["volume"].shift(1).rolling(vp).mean()
    f["vol_ratio"] = df["volume"] / vol_avg.replace(0, np.nan)

    # Volume z-score within a trailing window (includes current bar).
    prev_vol = df["volume"].shift(1).rolling(VOL_ZS_WINDOW)
    vol_mean = prev_vol.mean()
    vol_std = prev_vol.std()
    f["vol_z"] = ((df["volume"] - vol_mean) / vol_std.replace(0, np.nan))

    # Trailing percentile rank of the current bar's volume.
    f["vol_pct"] = df["volume"].rolling(VOL_PCT_WINDOW).rank(pct=True)
    f["vol_pct"] = f["vol_pct"].fillna(0.0)

    # ATR as a share of price and the detector's ATR spike ratio.
    atr = calculate_atr(df, BAD_LUCK_DETECTOR["atr_period"])
    f["atr_pct"] = atr / df["close"]
    atr_avg = atr.shift(1).rolling(BAD_LUCK_DETECTOR["atr_period"]).mean()
    f["atr_ratio"] = atr / atr_avg.replace(0, np.nan)

    # Drop expressed as a multiple of ATR (in price terms, so it is directly
    # comparable across instruments and timeframes).
    f["drop_atr"] = f["drop"] / f["atr_pct"].replace(0, np.nan)

    # Trailing session labels for activity profiling.
    f["hour"] = df.index.hour
    f["session"] = "Off"
    for name, (h0, h1) in SESSION_HOURS.items():
        f.loc[f["hour"].between(h0, h1), "session"] = name
    return f


def dynamic_drop_threshold(drop: pd.Series, win: int, q: float,
                           floor: float) -> pd.Series:
    """Trailing quantile of the drop series with a floor; no lookahead."""
    thresh = drop.rolling(win).quantile(q)
    return thresh.clip(lower=floor).fillna(np.inf)


def fmt_fwd(x: float) -> str:
    """Format a percentage with a sign."""
    return f"{x * 100:+.2f}%"


def forward_returns(f: pd.DataFrame, idx: np.ndarray, k: int) -> np.ndarray:
    """Forward close-to-close returns k bars ahead for the given index."""
    closes = f["close"].values
    horizon_low = f["low"].values
    horizon_high = f["high"].values
    out = np.full(len(idx), np.nan)
    for i, pos in enumerate(idx):
        end = pos + k
        if end >= len(closes):
            continue
        out[i] = closes[end] / closes[pos] - 1.0
    return out[np.isfinite(out)]


def adverse_favorable(f: pd.DataFrame, idx: np.ndarray, k: int):
    """Max adverse / max favorable excursion over the following k bars."""
    closes = f["close"].values
    lows = f["low"].values
    highs = f["high"].values
    adverse = np.full(len(idx), np.nan)
    favorable = np.full(len(idx), np.nan)
    for i, pos in enumerate(idx):
        end = min(pos + k, len(closes) - 1)
        if end <= pos:
            continue
        adverse[i] = (lows[pos + 1:end + 1].min() / closes[pos] - 1.0)
        favorable[i] = (highs[pos + 1:end + 1].max() / closes[pos] - 1.0)
    return adverse, favorable


def section_a1(out: list, data: dict) -> None:
    out.append("# Signal Feasibility & Threshold Calibration (Real Data)\n")
    out.append("## Scope\n")
    out.append("- **Data**: 2 years of REAL history exported from the FBS MT5 "
               "terminal (2024-09-23 .. 2026-09-23 UTC).\n")
    out.append(f"- **Symbols**: {', '.join(SYMBOLS)}.\n")
    out.append(f"- **Timeframes studied**: {', '.join(STUDY_TFS)} "
               "(each has a complete validated two-year real series).\n")
    out.append("- **M5 excluded**: the FBS demo terminal does not retain M5 "
               "history beyond ~14 days (2,740-2,870 bars, 2026-09-09 .. "
               "2026-09-23). A 14-day sample cannot support a feasibility "
               "conclusion, so M5 is documented as not evaluable with the "
               "current feed and left for future work.\n")
    out.append("- **No lookahead**: every indicator uses only the trailing "
               "window ending at (and in a few cases including) the current "
               "bar.\n")
    out.append("- **No production change**: config/strategy_params.py is not "
               "touched by this study.\n")

    out.append("\n## A1. Negative-return distribution (bar close-to-close "
               "drops, drop > 0 only)\n")
    out.append("| Sym | TF | n_drop_bars | p97.5 | p99 | p99.5 | p99.9 | "
               "max | median |\n")
    out.append("|-----|----|-------------|-------|-----|-------|-------|"
               "-----|--------|\n")
    for (sym, tf), feats in data.items():
        drops = feats["drop"].dropna()
        drops = drops[drops > 0]
        qs = drops.quantile([0.975, 0.99, 0.995, 0.999])
        out.append(
            f"| {sym} | {tf} | {len(drops)} | {qs[0.975]:.4f} | "
            f"{qs[0.99]:.4f} | {qs[0.995]:.4f} | {qs[0.999]:.4f} | "
            f"{drops.max():.4f} | {drops.median():.4f} |\n"
        )


def section_a2(out: list, data: dict) -> None:
    out.append("\n## A2. Volume behaviour\n")
    out.append("Ratio = current tick volume vs mean of the previous 20 bars "
               "(production formula). z-score and trailing percentile use a "
               "100-bar trailing window.\n")
    out.append("| Sym | TF | ratio p50 | ratio p90 | ratio p99 | z>2 | "
               "z>3 | z>4 | pct>95 | pct>98 | pct>99 | Asia | London | NYC |\n")
    out.append("|-----|----|-----------|-----------|-----------|-----|"
               "-----|-----|--------|--------|--------|------|--------|"
               "------|\n")
    for (sym, tf), f in data.items():
        rr = f["vol_ratio"].dropna()
        p50, p90, p99 = rr.quantile([0.5, 0.9, 0.99])
        z = f["vol_z"].dropna()
        nz = len(z)
        pct = f["vol_pct"]
        sess = {s: f.loc[f["session"] == s, "vol_ratio"].mean()
                for s in SESSION_HOURS}
        out.append(
            f"| {sym} | {tf} | {p50:.2f} | {p90:.2f} | {p99:.2f} | "
            f"{int((z > 2).sum())} | {int((z > 3).sum())} | "
            f"{int((z > 4).sum())} | {int((pct > 0.95).sum())} | "
            f"{int((pct > 0.98).sum())} | {int((pct > 0.99).sum())} | "
            f"{sess['Asia']:.2f} | {sess['London']:.2f} | "
            f"{sess['New York']:.2f} |\n"
        )


def section_a3(out: list, data: dict) -> None:
    out.append("\n## A3. ATR behaviour and drop-as-ATR-multiple\n")
    out.append("ATR % = ATR(14) / close. drop/ATR = bar drop expressed as a "
               "multiple of the trailing ATR(14).\n")
    out.append("| Sym | TF | ATR% p25 | ATR% p50 | ATR% p75 | ATR% p99 | "
               "drop>=2A | drop>=3A | drop>=4A | drop>=5A |\n")
    out.append("|-----|----|----------|----------|----------|----------|"
               "----------|----------|----------|----------|\n")
    for (sym, tf), f in data.items():
        ap = f["atr_pct"].dropna()
        qs = ap.quantile([0.25, 0.5, 0.75, 0.99])
        da = f["drop_atr"].dropna()
        out.append(
            f"| {sym} | {tf} | {qs[0.25]:.4f} | {qs[0.5]:.4f} | "
            f"{qs[0.75]:.4f} | {qs[0.99]:.4f} | "
            f"{int((da >= 2).sum())} | {int((da >= 3).sum())} | "
            f"{int((da >= 4).sum())} | {int((da >= 5).sum())} |\n"
        )


def section_a4(out: list, data: dict) -> None:
    out.append("\n## A4. Joint drop x volume occurrence (signals per matrix "
               "cell)\n")
    out.append("Each cell = number of candles satisfying BOTH the drop "
               "candidate and the volume screen. Counts are over the full "
               "two-year window (trading hours are NOT applied here; that is "
               "left to the backtest stage). xxx/yyy = year1/year2 split.\n")
    for tf in STUDY_TFS:
        drops = DROP_CANDIDATES[tf]
        screens = ([f"ratio>{r}" for r in VOLUME_RATIOS] +
                   [f"z>{z}" for z in VOLUME_Z] +
                   [f"pct>{int(p*100)}" for p in VOLUME_PCT])
        out.append(f"\n### A4.{tf}\n")
        out.append("| drop | " + " | ".join(screens) + " |\n")
        out.append("|------|" + "-----|" * len(screens) + "\n")
        for (sym, tf2), f in data.items():
            if tf2 != tf:
                continue
            year = f.index.year
            for d in drops:
                cells = []
                for r in VOLUME_RATIOS:
                    m = (f["drop"] >= d) & (f["vol_ratio"] >= r)
                    cells.append(f"{int(m.sum())}/{int((m & (year == year.min())).sum())}"
                                 f"/{int((m & (year == year.max())).sum())}")
                for z in VOLUME_Z:
                    m = (f["drop"] >= d) & (f["vol_z"] >= z)
                    cells.append(f"{int(m.sum())}/{int((m & (year == year.min())).sum())}"
                                 f"/{int((m & (year == year.max())).sum())}")
                for p in VOLUME_PCT:
                    m = (f["drop"] >= d) & (f["vol_pct"] >= p)
                    cells.append(f"{int(m.sum())}/{int((m & (year == year.min())).sum())}"
                                 f"/{int((m & (year == year.max())).sum())}")
                out.append(f"| {d:.4f} | " + " | ".join(cells) + " |\n")

    out.append("\n### A4. Dynamic trailing-percentile drop thresholds "
               "(with floor, no lookahead)\n")
    out.append("Threshold = max(trailing quantile of drop series, floor). "
               "Median applied threshold and signal count shown. Windows are "
               "in bars (1w/2w/1mo).")
    for tf in STUDY_TFS:
        wins = ROLLING_WINDOWS[tf]
        floor = DYNAMIC_FLOOR[tf]
        labels = ["1w", "2w", "1mo"]
        out.append(f"\n#### A4.D.{tf} (floor {floor:.4f})\n")
        out.append("| Sym | q | " +
                   " | ".join(f"{lbl}: median-thr | {lbl}: count"
                              for lbl in labels) + " |\n")
        out.append("|-----|---|" + "-----|---|" * len(labels) + "\n")
        for (sym, tf2), f in data.items():
            if tf2 != tf:
                continue
            for q in [0.99, 0.995, 0.999]:
                cols = []
                for win in wins:
                    th = dynamic_drop_threshold(f["drop"], win, q, floor)
                    med_th = th[np.isfinite(th)].median()
                    cnt = int((f["drop"] >= th).sum())
                    cols.append(f"{med_th:.4f} | {cnt}")
                out.append(f"| {sym} | {q} | " + " | ".join(cols) + " |\n")


def shortlist_configs(data: dict) -> list:
    """Pick a small, defensible shortlist for the forward-edge stage (B1).

    Selection logic: fixed-drop candidates that produced a year1/year2
    balanced signal pool (>= ~20 signals each year) with a volume ratio or
    z-screen, capped to a few per timeframe so the report stays readable.
    """
    candidates = []
    min_per_year = 15
    for (sym, tf), f in data.items():
        year = f.index.year
        y1 = year.min()
        for d in DROP_CANDIDATES[tf]:
            for r in [1.5, 2.0]:
                m = (f["drop"] >= d) & (f["vol_ratio"] >= r)
                n1 = int((m & (year == y1)).sum())
                n2 = int((m & (year != y1)).sum())
                if n1 >= min_per_year and n2 >= min_per_year:
                    candidates.append({
                        "sym": sym, "tf": tf, "drop": d, "rule": r,
                        "kind": "ratio", "signals": n1 + n2,
                    })
            for z in [2.0]:
                m = (f["drop"] >= d) & (f["vol_z"] >= z)
                n1 = int((m & (year == y1)).sum())
                n2 = int((m & (year != y1)).sum())
                if n1 >= min_per_year and n2 >= min_per_year:
                    candidates.append({
                        "sym": sym, "tf": tf, "drop": d, "rule": z,
                        "kind": "z", "signals": n1 + n2,
                    })
    # Cap per timeframe, preferring lower drop thresholds (more signals).
    capped = {}
    for c in candidates:
        capped.setdefault((c["sym"], c["tf"]), [])
        capped[(c["sym"], c["tf"])].append(c)
    out = []
    for key, cs in capped.items():
        cs.sort(key=lambda c: (c["signals"]))
        out.extend(cs[-2:])
    out.sort(key=lambda c: (c["tf"], c["sym"], c["drop"]))
    return out


def random_baseline(f: pd.DataFrame, n: int, k: int) -> dict:
    """Mean/max of forward-return stats over FWD_DRAWS random draws."""
    rng = np.random.default_rng(RANDOM_SEED)
    usable = np.arange(len(f) - k)
    means, meds, poss = [], [], []
    for _ in range(FWD_DRAWS):
        idx = rng.choice(usable, size=min(n, len(usable)), replace=False)
        fr = forward_returns(f, idx, k)
        if len(fr):
            means.append(fr.mean())
            meds.append(np.median(fr))
            poss.append((fr > 0).mean())
    return {
        "mean": float(np.mean(means)) if means else np.nan,
        "max_mean": float(np.max(means)) if means else np.nan,
        "median": float(np.mean(meds)) if meds else np.nan,
        "pct_pos": float(np.mean(poss)) if poss else np.nan,
    }


def section_b1(out: list, data: dict) -> None:
    out.append("\n## B1. Forward-return edge vs random baseline\n")
    out.append("For each shortlist config the forward close-to-close returns "
               "are measured k bars ahead (k in bars: 15/30/60/120). Edge = "
               "candidate mean fwd return minus the mean of an "
               "identically-sized randomly drawn baseline. All stats are "
               "daily-bar independent; sign and magnitude shown raw. A "
               "candidate is only interesting if the edge is positive, "
               "stable across years, and its pct-positive exceeds the "
               "baseline.\n")
    cands = shortlist_configs(data)
    if not cands:
        out.append("\n_(No candidate reached the year1/year2 >= 15 signal "
                   "requirement. Feasibility is therefore negative under the "
                   "fixed-drop volume screens considered here.)_\n")
        return
    out.append("\n| Sym | TF | drop | screen | signals | fwd | cand mean | "
               "cand med | cand %>0 | base max | edge(k) |\n")
    out.append("|-----|----|------|--------|---------|-----|-----------|"
               "---------|----------|----------|---------|\n")
    for c in cands:
        f = data[(c["sym"], c["tf"])]
        m = (f["drop"] >= c["drop"])
        if c["kind"] == "ratio":
            m &= f["vol_ratio"] >= c["rule"]
        else:
            m &= f["vol_z"] >= c["rule"]
        idx = np.flatnonzero(m.values)
        for k in FWD_HORIZONS:
            fr = forward_returns(f, idx, k)
            if len(fr) < 5:
                continue
            base = random_baseline(f, len(idx), k)
            edge = fr.mean() - base["mean"]
            out.append(
                f"| {c['sym']} | {c['tf']} | {c['drop']:.4f} | "
                f"{c['kind']}{c['rule']:.2f} | {len(idx)} | {k} | "
                f"{fmt_fwd(fr.mean())} | {fmt_fwd(np.median(fr))} | "
                f"{np.mean(fr > 0) * 100:.1f}% | "
                f"{fmt_fwd(base['max_mean'])} | {fmt_fwd(edge)} |\n"
            )

    out.append("\n### B1. Maximum adverse / favorable excursion "
               "(60-bar horizon), full signal pool\n")
    out.append("MAE = worst low-to-entry drawdown; MFE = best high-to-entry "
               "run-up. Both normalized to % of entry close.\n")
    out.append("| Sym | TF | drop | screen | signals | mean MAE | mean MFE |\n")
    out.append("|-----|----|------|--------|---------|----------|----------|\n")
    for c in cands:
        f = data[(c["sym"], c["tf"])]
        m = (f["drop"] >= c["drop"])
        m &= f["vol_ratio"] >= c["rule"] if c["kind"] == "ratio" else f["vol_z"] >= c["rule"]
        idx = np.flatnonzero(m.values)
        adv, fav = adverse_favorable(f, idx, 60)
        if adv.size and np.isfinite(adv).any():
            out.append(
                f"| {c['sym']} | {c['tf']} | {c['drop']:.4f} | "
                f"{c['kind']}{c['rule']:.2f} | {len(idx)} | "
                f"{fmt_fwd(np.nanmean(adv))} | {fmt_fwd(np.nanmean(fav))} |\n"
            )


def section_a5(out: list, data: dict) -> None:
    out.append("\n## A5. Reversal pattern and full-detector condition stack\n")
    out.append("Production detector = drop AND volume-spike(2x vs 20) AND "
               "ATR-spike(1.5x vs 14) AND reversal pattern, inside trading "
               "hours and away from news. Here we relax ONLY the drop and "
               "volume thresholds while keeping the rest of the stack, to see "
               "how many signals a relaxed real detector could produce over "
               "two years (news/trading-hours not applied yet).\n")
    out.append("| Sym | TF | drop | vol | drop+vol | +ATR spike | +pattern | "
               "full(relaxed) |\n")
    out.append("|-----|----|------|-----|-----------|------------|-----------|"
               "---------------|\n")
    for tf in STUDY_TFS:
        chosen_one = DROP_CANDIDATES[tf][2]
        for (sym, tf2), f in data.items():
            if tf2 != tf:
                continue
            for d, r in [(chosen_one, 1.5), (chosen_one, 2.0)]:
                m_drop = f["drop"] >= d
                m_vol = f["vol_ratio"] >= r
                m_atr = f["atr_ratio"] >= BAD_LUCK_DETECTOR["atr_multiplier"]
                m_pat = is_reversal_pattern(
                    f, BAD_LUCK_DETECTOR["reversal_patterns"]).astype(bool).values
                dv = (m_drop & m_vol).sum()
                dva = (m_drop & m_vol & m_atr).sum()
                dvap = (m_drop & m_vol & m_atr & m_pat).sum()
                out.append(
                    f"| {sym} | {tf} | {d:.4f} | {r:.1f} | {dv} | {dva} | "
                    f"{int((m_drop & m_atr & m_pat).sum())} | {dvap} |\n"
                )
    out.append("\nThe **full(relaxed)** column is the closest real estimate "
               "of how many live 'bad-luck moment' trades the configured "
               "stack would fire at these relaxed thresholds. Zero here means "
               "the strategy premise is not viable at any tested operand.\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze signal feasibility on real historical data.")
    parser.add_argument("--out", default="reports/signal_feasibility_report.md")
    args = parser.parse_args()

    data = load_data()
    out = []
    for (sym, tf), df in data.items():
        data[(sym, tf)] = prepare_features(df, tf)
        print(f"features ready for {sym} {tf}: {len(df)} bars", flush=True)

    section_a1(out, data)
    section_a2(out, data)
    section_a3(out, data)
    section_a4(out, data)
    section_a5(out, data)
    section_b1(out, data)
    out.append("\n---\n*Generated by scripts/analyze_signal_feasibility.py "
               "on real terminal data. This report is research evidence; it "
               "does not change production behaviour.*\n")

    dst = Path(args.out)
    dst.write_text("".join(out), encoding="utf-8")
    print(f"report written: {dst.resolve()}")
    print("shortlist candidates for B1:")
    for c in shortlist_configs(data):
        print(f"  {c['sym']} {c['tf']} drop={c['drop']} "
              f"{c['kind']}{c['rule']} signals={c['signals']}")


if __name__ == "__main__":
    main()