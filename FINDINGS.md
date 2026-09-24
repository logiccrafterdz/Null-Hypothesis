# Key Findings

A data-driven summary of what eleven phases of quant research proved.
Every number below is reproducible from the code and reports in this
repository.

---

## Finding 1: The Original Premise is Dead

The "Bad Luck Moment" — a 3% single-bar price drop on M15 — barely exists on
the instruments tested.

| Metric | Value |
|---|---|
| 99th-percentile M15 drop, EURUSD | 0.16% |
| 99th-percentile M15 drop, GBPJPY | 0.20% |
| 99th-percentile M15 drop, XAUUSD | 0.59% |
| Largest single M15 drop in 2 years (XAUUSD) | 3.6% (once) |
| Complete production-detector signals in 2 years | **0** |

The drop condition alone kills the premise. Adding the volume and volatility
conditions makes it structurally impossible. The original "Bad Luck Moment" as
defined does not exist on real data.

## Finding 2: Relaxed Thresholds Have No Edge

Relax the drop and volume conditions and signals appear — but they carry no
edge.

| Configuration | Signals / 2y |
|---|---|
| XAUUSD M15 drop 0.2% + vol 1.5x | 983 |
| XAUUSD M30 drop 0.25% + vol 1.5x | 631 |
| XAUUSD H1 drop 0.3% + vol 1.5x | 384 |

- Forward closed-bar returns indistinguishable from a random baseline.
- Realised PNL (production trade management): **uniformly negative** —
  XAUUSD -4.3% .. -35.7%, EURUSD -0.9% .. -4.8%.
- Profit factors 0.07 .. 0.99 against the 2.0 success bar.
- No configuration positive in both year-1 and year-2.

## Finding 3: GBPJPY is Untradeable for Small Accounts

A structural barrier, not a parameter problem.

| Symbol | Approx capital for one 0.01 lot (2% risk / 1.5% stop) |
|---|---|
| EURUSD | ~0.8k |
| XAUUSD | ~2.0k |
| GBPJPY | **~127k** |

GBPJPY refused 100% of signals even at a $100,000 account size.

## Finding 4: EURUSD M15 is Perfectly Efficient

The most conclusive efficiency result in the project.

- 2,000 random strategies generated on EURUSD M15.
- **Zero** survived the primary filter — not even a false positive.
- The luck baseline itself was deeply negative (mean -18.2%).
- FDR correction found nothing to correct: nothing survived to be wrong.

EURUSD M15 is the strongest evidence in this study that liquid FX is
informationally efficient at the intraday level.

## Finding 5: Random Mining Finds Only Directional Beta

4,000 strategies were generated and tested across two assets (2,000 each on
XAUUSD and EURUSD) against an 800-strategy-per-asset luck baseline.

```
XAUUSD: 2,000 generated → 3 primary → 2 robustness → 2 FDR+p95 → 2 top N
EURUSD: 2,000 generated → 0
```

| Survivor | Direction | Trades | Win% | PF | Return% | MaxDD% | Sharpe | p(luck) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| XAUUSD_M15_56202 | LONG | 178 | 65.2 | 1.73 | 10.9 | 2.4 | 1.26 | 0.0275 |
| XAUUSD_M15_28590 | LONG | 224 | 50.0 | 1.33 | 12.5 | 10.6 | 0.55 | 0.0238 |

Both survivors are **LONG-only on a rising asset**. The SHORT mirror test on
the leader lost -12.86% while LONG made +10.91%. Buy-and-hold gold made
**+62.93%** over the same window — roughly 6x the strategy's +10.9%. The
survival rate of 0.05% is a consequence of statistical rigor; the directional
bias of the survivors is the finding that matters.

## Finding 6: The "65% Win Rate" Illusion

The leader's headline metric was an artifact of construction.

| Exit reason | N | Win% within | Contribution |
|---|---:|---:|---:|
| Take Profit (fixed +0.47%) | 85 | 100% | +27.39% |
| Max Duration timeout | 86 | 31.4% | -11.53% |
| Stop Loss | 2 | 0% | -3.78% |
| Trailing Stop | 5 | 80% | +1.28% |

- Tight take-profit (+0.5%) clips winners early → high win rate.
- Losers extend to max duration → hidden bleed.
- Skewness -2.16 (fat left tail), excess kurtosis +7.41.
- Remove the best 5 trades → whole-book return halves (gross).
- The win rate is a presentation artifact, not an edge.

## Finding 7: The Engine is the Real Product

What survived the eleven phases is a scientific research instrument.

- **133+ passing tests**: indicators, backtester, mining validation, risk,
  broker abstraction, end-to-end workflows.
- **Real data pipeline**: FBS MT5 history, UTC-normalized, with automated
  quality validation. Synthetic data used strictly for pipeline verification,
  never as evidence.
- **Statistical correction**: Benjamini-Hochberg FDR, Monte Carlo luck
  baselines, percentile rankings, p(luck).
- **Forensic toolkit**: verbose-sim validation gate, SHORT-mirror, buy-and-hold
  controls, regime analysis, walk-forward OOS, trade-level exit anatomy.
- **Reproducible methodology**: every number in every report can be
  regenerated from scripts in this repository.

This engine can test ANY future hypothesis honestly. That is the achievement
the project was really building all along.

---

*Verdicts across all phases: Phase 7 NO-GO (premise dead), Phase 8 NO-GO
(no edge), Phase 9 NO-GO (pivots fail), Phase 10 ambiguous (2/4000 survivors),
Phase 11 B-DIRECTIONAL BETA (not alpha). No exploitable intraday M15 alpha was
found on XAUUSD or EURUSD using the tested methodologies.*