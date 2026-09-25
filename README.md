# Null Hypothesis

### A Quant Research Engine for Testing Intraday Alpha

**Result: no robust, economically meaningful, out-of-sample exploitable alpha
was detected within the tested research space.**

[![Tests](https://img.shields.io/badge/tests-133%20passed-brightgreen)](#)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](#)
[![Verdict](https://img.shields.io/badge/alpha-not%20detected-red)](#)
[![Integrity](https://img.shields.io/badge/scientific%20integrity-100%25-gold)](#)

---

## What Is This?

This is **not a trading strategy**. It is a **scientific research engine** that
applies systematic statistical and robustness testing to a simple question:
can exploitable intraday alpha be found on liquid FX pairs using a randomized,
unbiased strategy search?

The project ran eleven phases: a production-grade trading system was built and
audited, validated against real broker data, pushed through threshold
calibration and strategy pivots, and finally mined with thousands of randomly
generated strategies. The survivors were then forensically autopsied.

**The original trading hypothesis did not survive. The research protocol did
its job.**

## The Result

Scoped, defensible, reproducible:

> **No robust, economically meaningful, out-of-sample exploitable alpha was
> detected on XAUUSD/EURUSD M15 within the tested search space and experimental
> protocol.** The two survivors of the mining gauntlet were shown to be
> directional beta — long-only exposure to a rising asset — not market-neutral
> alpha. This experiment does **not** establish market-wide efficiency.

For context, over the same two-year period:

| Control | Net return |
|---------|-----------:|
| Passive buy-and-hold of gold | +62.93% |
| Best mined strategy (LONG) | +10.91% |
| SHORT mirror of the same strategy | −12.86% |

## Research Funnel

```text
4,000 candidates
      ↓
  basic validity
      ↓
 statistical filters
      ↓
 robustness tests
      ↓
 out-of-sample
      ↓
       2
   survivors
      ↓
 forensic analysis
      ↓
  0 independent alpha
      ↓
  2 directional beta
```

The 4,000 figure is **2,000 generated candidates per asset × 2 assets**
(XAUUSD + EURUSD), with a further **800 random-entry baselines per asset** used
as the luck control. A single session of
`run_mining_session.py --quota 2000 --luck 800` over the default asset list
reproduces exactly this run.

## Quick Summary

| Phase | What We Did | Result |
|-------|-------------|--------|
| 1–6 | Built production trading system | ✅ 133 tests, audit 92/100 |
| 7 | Real data validation | ❌ 0 signals in 2 years |
| 8 | Threshold calibration | ❌ No edge found |
| 9 | Strategy pivot | ❌ No edge found |
| 10 | Random mining (4,000 candidates) | ⚠️ 2 survivors |
| 11 | Forensic analysis | ❌ Both are beta, not alpha |

## The Story

- Read the full journey: [JOURNEY.md](JOURNEY.md)
- Read the key findings: [FINDINGS.md](FINDINGS.md)
- Explore the visual showcase: [GitHub Pages](https://logiccrafterdz.github.io/Null-Hypothesis/)

## Scope and Limitations

This result is deliberately bounded. It covers only what was actually tested:

| Dimension | Value |
|-----------|-------|
| Instruments | XAUUSD, EURUSD (GBPJPY in early feasibility phases only) |
| Timeframe | M15 |
| Historical period | 2 years of real broker history, per instrument |
| Data source | FBS MetaTrader 5 history export, resampled to M15 |
| Strategy search space | Random strategies from the condition library (~50 templates), 2–5 conditions each, `and`/`or`/`mixed` logic, random direction |
| Generated candidates | 4,000 (2,000 per asset × 2 assets) |
| Luck baseline | 1,600 random-entry strategies (800 per asset) |
| Trading capital | $10,000 simulated |
| Position sizing | 2% risk per trade, max 2 open positions, minimum-lot gating |
| Trade management | Market orders; stop 0.5–3%, take-profit 0.5–5%, optional trailing, max duration 5–50 bars (per-strategy random exits) |
| Transaction costs | Commission 0.02% of notional per side, spread 0.01% |
| Slippage model | 0.01% adverse slippage on entry and exit |
| Validation methodology | Monte Carlo luck baselines, per-year robustness stress, walk-forward out-of-sample |
| Multiple-testing correction | Benjamini-Hochberg FDR + p95 luck percentile |
| Forensic checks | SHORT mirror, buy-and-hold control, regime analysis, trade-level exit anatomy |

> **This experiment does not establish market-wide efficiency. It establishes
> only that no robust exploitable alpha was detected within the specified
> search space and experimental protocol.**

## What Would Change the Conclusion?

The conclusion would be reconsidered if a strategy **outside the current search
space** demonstrates statistically significant, economically meaningful, and
out-of-sample performance after realistic transaction costs and **independent
validation** (unseen data and/or an external protocol).

No single negative experiment closes the question. The engine's value is that
it can re-open the question honestly: any future hypothesis can be pushed
through the same statistical and forensic pipeline, and the record kept.

## Architecture

```
null-hypothesis/
├── src/               # Core engine
│   ├── core/          #   data_fetcher, market_analyzer, decision_engine,
│   │                  #   risk_manager, trade_executor
│   ├── strategies/    #   BaseStrategy + filters (trend, volatility, news)
│   ├── api/           #   broker_interface, mt5_connector
│   └── utils/         #   indicators, logger, helpers, notifications
├── backtesting/       # backtester, monte_carlo, walk_forward
├── scripts/           # data collection, reporting, mining, forensics
├── dashboard/         # Streamlit visualization
├── config/            # settings, strategy parameters, credentials
├── reports/           # all research reports (permanent record)
└── tests/             # 133+ tests
```

Each component has a single responsibility. Broker access goes through a
unified interface. Dependencies are injected; configuration is externalized.
The entire system is instrumented for honest, reproducible research.

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Verify the test suite
python -m pytest tests/ -q

# 3. Real data (option A): export MT5 history to data/raw/
python scripts/download_mt5_history.py --symbols XAUUSD GBPJPY EURUSD --days 730

# 3. Synthetic fixtures (option B): pipeline-validation data only
python scripts/generate_synthetic_data.py --symbols XAUUSD GBPJPY EURUSD --days 365

# 4. Run the corrected backtester on one asset
python main.py --mode backtest --asset XAUUSD --days 365

# 5. Validate real-data quality in data/raw
python scripts/validate_real_data.py

# 6. Mining / Chaos Discovery Engine (Phase 10 research)
#    --quota and --luck are per-asset; a session over the default two assets
#    generates 2 x 2000 = 4,000 candidates and 2 x 800 luck baselines.
python scripts/run_mining_session.py --quota 2000 --luck 800

# 7. Forensic autopsy of a mined survivor (Phase 11)
python scripts/run_phase_11_forensics.py
```

For the unavoidable disclaimer: if you want to use real money,
`python main.py --mode live --assets XAUUSD GBPJPY`. We do not recommend it.

## Research Reports

All reports are preserved in the `reports/` directory as a permanent
scientific record:

| Report | Contents |
|--------|----------|
| `post_fix_backtest_report.md` | Backtest pipeline validation |
| `real_history_backtest_report.md` | Phase 7: real-data verification |
| `threshold_calibration_report.md` | Phase 8: NO-GO synthesis |
| `signal_feasibility_report.md` | Phase 8: signal feasibility study |
| `research_candidate_backtests.md` | Phase 9: pivot research |
| `mining_summary.md` | Phase 10: mining session funnel |
| `top_strategies_report.md` | Phase 10: survivors |
| `phase_11_final_verdict.md` | Phase 11: forensic verdict — DIRECTIONAL BETA |
| `strategy_56202_*.md` | Phase 11: autopsy, bias, temporal, forensics, OOS |

The reports exist so the conclusion is auditable, not asserted: every number
in this README can be traced to a file in `reports/` and regenerated from the
code in this repository.

## The Final Verdict

After 4,000 generated strategies, 2 years of real data, 11 phases, and a
forensic autopsy, the engine concluded:

> **B — DIRECTIONAL BETA.** The surviving strategies were long-only bets on a
> rising asset, not market-neutral alpha. This was established with
> falsifiable checks: a SHORT mirror of the identical rules lost money, a
> passive buy-and-hold outperformed every mined strategy, and holdout
> performance collapsed in the one falling quarter. Deployment was not
> recommended.

## License

MIT. See the [LICENSE](https://github.com/logiccrafterdz/Null-Hypothesis/blob/master/LICENSE) file.

## Disclaimer

This project is a research tool and educational resource. It is NOT financial
advice. No trading strategy is guaranteed to be profitable. Past performance
does not indicate future results. Nothing here should be taken as a claim that
any particular market is or is not efficient.