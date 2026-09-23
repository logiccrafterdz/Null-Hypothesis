# Threshold Calibration Report — Signal Feasibility on Real Data

**Project**: Phoenix Protocol — "Bad Luck Moment" / Capitulation Reversal premise
**Study period**: 2024-09-23 .. 2026-09-23 UTC (2 years of real FBS MT5 data)
**Symbols**: XAUUSD, GBPJPY, EURUSD — **Timeframes**: M15, M30, H1 (M5 excluded: ~14 days of retention only, documented below)
**Status**: **NO-GO for production deployment** — flat conclusion, no promoted candidate.

---

## 1. Question 1 — Is the ORIGINAL 3%-drop / 2x-volume / 1.5x-ATR / reversal-pattern detector viable on real M15 data?

**No.** The full production detector stack fires **0 times** over two years
on all three symbols. The and-gate is killed twice over:

- The 99-th percentile of real 15-min drops is far below 3% for the FX pairs
  (GBPJPY p99 = 0.20%, EURUSD p99 = 0.16%; XAUUSD p99 = 0.59%). Across the
  entire corpus the biggest single-bar drop fit on record is 3.6% (XAUUSD,
  once in two years) — and that bar failed the volume condition.
- Even if the drop/volume/ATR conditions were relaxed to frequent levels, the
  **same-bar reversal pattern is structurally incompatible with a large drop
  bar**: reversal patterns appear on ~27% of all bars but on only ~1% of bars
  with a large drop. Relaxed full-stack tests (drop 0.003-0.008, volume 1.5x)
  still produced **0 complete signals** on every timeframe.

Under "0 signals" the strategy is behaviourally identical to no strategy:
trading hours, news and randomness gates never even get consulted.

## 2. Question 2 — Are there threshold/timeframe options (fixed or dynamic) with enough signals to trade?

**Frequency yes; profitability no.** Relaxing ONLY the drop and volume
conditions produces tradable cadences on real data:

| TF | Emblematic config | Signals / 2y | Quarterly spread |
|----|-------------------|--------------|------------------|
| M15 | XAUUSD drop 0.2% + vol 1.5x | 983 | 7 .. 178 |
| M30 | XAUUSD drop 0.25% + vol 1.5x | 631 | 7 .. 109 |
| H1  | XAUUSD drop 0.3% + vol 1.5x | 384 | 2 .. 60 |

Dynamic trailing-percentile drop thresholds (1w/2w/1mo windows, quantiles
0.99/0.995/0.999, floored) also produce steady signal pools (e.g. XAUUSD M15
q0.99 1w -> ~515 signals/2y) without a fixed hard threshold. So "multiple
threshold/timeframe options" with usable frequency do exist.

## 3. Question 3 — Do these signals have a plausible reversal (capitulation) edge?

**No.** Forward closed-bar returns at 15/30/60/120 bars for every shortlisted
candidate are statistically indistinguishable from an identically-sized random
baseline:

- Mean edges range ~ -0.2% .. +0.2% with the majority negative or within
  one standard error of zero; %-positive mostly 47-58% (random coin flip).
- Year-1 vs year-2 splits show no config with positive returns in BOTH years.
- The realisation with production trade management (stop 1.5%, TP 3%,
  trailing, max 15 bars) is uniformly negative: XAUUSD -35.7% .. -4.3%,
  EURUSD -4.8% .. -0.9%, with profit factors 0.07 .. 0.99 vs the 2.0 success
  bar. Exit anatomy: 74-100% of trades time out at max-duration near 0 while
  19-26% (XAUUSD) hit the -1.5% stop.

The "buy the capitulation bar" premise does not show reversal edge in two
years of real data at any threshold/timeframe combination tested.

## 4. Question 4 — Is any single candidate paper-trade ready?

**No.** The closest numeric pool (XAUUSD M15/M30/H1 drop+vol 1.5x) still loses
money and fails the success criteria (min PF 2.0, min win 60%, max DD 15%).
No candidate therefore qualifies for paper-trading, and under the study's own
honesty rules it would be misleading to progress without an edge.

## 5. Question 5 — Proposed production candidate

**None.** The study proposes **flat NO-GO**:

1. The current detector cannot trade at all on real data (zero signals).
2. No relaxed alternative tested has a forward edge or positive realised
   return.
3. GBPJPY is additionally untradeable at any tested account size up to 100k
   due to minimum-lot refusals (0.01 lot needs ~127k at 2% risk / 1.5% stop
   with a 100000 contract size); EURUSD needs >= ~1k and XAUUSD >= ~2k for
   the same sizing.

## 6. Minimum-lot viability summary

| Symbol | Approx capital needed for one 0.01 lot (2% risk / 1.5% stop) | Notes |
|--------|----------------------------------------------------------------|-------|
| EURUSD | ~0.8k | Fine at all tested scenarios |
| XAUUSD | ~2.0k | Fine at all tested scenarios |
| GBPJPY | ~127k | 100% refusal even at 100k |

## 7. What was ruled out and why (no-blind-fitting evidence)

- **Curve-fitting**: no threshold was chosen "because it backtests well";
  drop candidates were pre-fixed grids spanning ~2x on each side of the
  production value and dynamic thresholds use trailing windows only.
- **Synthetic data**: none used as evidence. Only real terminal exports.
- **Production configuration**: untouched. Research candidates are isolated
  under `config/research_candidates/` and are explicitly NOT promoted.
- **M5**: excluded because the FBS demo terminal only retains ~14 days of M5
  (~2,800 bars) — five candidates on that dataset would be statistically
  meaningless. It is re-evaluable if a longer real M5 feed becomes available.

## 8. Recommended next steps (research, not deployment)

- Re-frame the premise: verify whether ANY entry rule on these assets shows
  an out-of-sample edge before further threshold work (e.g. trend-following
  intraday filters on the same real corpus).
- If the capitulation-reversal idea is retained, restructure the detector so
  the reversal signal is evaluated AFTER the capitulation bar (next-bar entry),
  keeping a strict no-lookahead split, and re-run feasibility before any
  quality threshold.

## 9. Artifacts

- Evidence: `reports/signal_feasibility_report.md`,
  `reports/research_candidate_backtests.md`.
- Research configs: `config/research_candidates/*.yaml`.
- Scripts: `scripts/analyze_signal_feasibility.py`,
  `scripts/run_research_backtests.py`.

---
*Synthesis generated 2026-09-23 from real-data evidence. Verdict: NO-GO.*