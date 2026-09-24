# Null Hypothesis 🔬

### A Quant Research Engine That Proved Its Own Null Hypothesis

> "In science, proving that something DOESN'T work is just as valuable
> as proving that it does."

[![Tests](https://img.shields.io/badge/tests-133%20passed-brightgreen)](#)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](#)
[![Verdict](https://img.shields.io/badge/alpha-NOT%20FOUND-red)](#)
[![Integrity](https://img.shields.io/badge/scientific%20integrity-100%25-gold)](#)

---

## What Is This?

This is NOT a trading strategy. This is a **scientific research engine** that
set out to build a trading strategy and instead proved, with mathematical
rigor, that no exploitable intraday alpha exists on XAUUSD/EURUSD M15 using the
tested methodologies.

The journey took 11 phases, tested 4,000+ random strategies, analyzed 2 years
of real market data, and arrived at an honest conclusion: **the market is
efficient.**

We set out to find alpha. We found the truth instead.
And the truth is more valuable.

## The Story

- Read the full journey: [JOURNEY.md](JOURNEY.md)
- Read the key findings: [FINDINGS.md](FINDINGS.md)
- Explore the visual showcase: [GitHub Pages](https://logiccrafterdz.github.io/phoenix-protocol/)

## Quick Summary

| Phase | What We Did | Result |
|-------|-------------|--------|
| 1-6 | Built production trading system | ✅ 133 tests, audit 92/100 |
| 7 | Real data validation | ❌ 0 signals in 2 years |
| 8 | Threshold calibration | ❌ No edge found |
| 9 | Strategy pivot | ❌ No edge found |
| 10 | Random mining (4,000 strategies) | ⚠️ 2 survivors |
| 11 | Forensic analysis | ❌ Both are beta, not alpha |

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
python scripts/run_mining_session.py --quota 2000 --luck 800

# 7. Forensic autopsy of a mined survivor (Phase 11)
python scripts/run_phase_11_forensics.py
```

For the unavoidable disclaimer: if you want to actually use real money,
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

## The Final Verdict

After 4,000 generated strategies, 2 years of real data, 11 phases, and a
forensic autopsy, the engine concluded:

> **B — DIRECTIONAL BETA.** The surviving strategies are long-only bets on a
> rising asset, not market-neutral alpha. Proving a null hypothesis is a
> scientific achievement: we built a system that refused to lie to us, and we
> saved potential users from deploying a disguised-beta strategy at scale.

## License

MIT. Do whatever you want with it. It's probably not worth the effort anyway.

## Disclaimer

This project is a research tool and educational resource. It is NOT financial
advice. No trading strategy is guaranteed to be profitable. Past performance
does not indicate future results.

---

Built because someone said it couldn't be done.
And it couldn't. That was the answer.