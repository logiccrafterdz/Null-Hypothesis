# Phoenix Protocol - Real Historical Data Backtest Report

> Source: REAL market history exported from the FBS MetaTrader 5 terminal (Demo account). This is a strategy evaluation on historical broker data, not a live-performance claim.

## A. Environment

- Python: 3.14.0
- Platform: win32
- Command: `python scripts/generate_real_report.py --days 730 --capital 20000.0`
- Data source: real M15 broker history (`data/raw/*_M15.csv`, exported by `scripts/download_mt5_history.py`)
- Data fetch mode: `DATA_SOURCE=local` (no broker fetch during backtest)
- Symbols: XAUUSD, GBPJPY, EURUSD
- Timeframe: M15 (main)
- Date range: 2024-09-23 20:32:47 to 2026-09-23 20:32:47
- Server time: FBS GMT+3 (empirically measured), converted to UTC; fixture datetimes are naive UTC

- Candles per asset (XAUUSD): 47217
- Candles per asset (GBPJPY): 49665
- Candles per asset (EURUSD): 49666

## B. Strategy Configuration

| Parameter | Value |
|---|---|
| drop_threshold | 0.03 |
| volume_multiplier | 2.0 |
| atr_multiplier | 1.5 |
| reversal patterns | hammer, doji, engulfing_bullish, morning_star, piercing |
| entry_probability | 0.6 |
| use_cryptographic_rng | True |
| stop_loss_pct | 0.015 |
| take_profit_pct | 0.03 |
| trailing stop enabled | True |
| max_duration_candles | 15 |
| position_size_risk | 0.02 |
| max_open_trades | 2 |
| max_daily_loss | 5.00% |
| max_weekly_loss | 10.00% |
| cooldown_after_loss | 3 trades |

Risk limits are SIMULATED during this backtest (daily/weekly loss caps, cooldown, max open) via the same thresholds as the live `RiskManager`.

## C. Signal-to-Execution Funnel (risk limits enforced)

Primary scenario: capital = **20,000 USD**. `signals` are detector verdicts (deterministic); the randomness engine is non-deterministic by design, so entry splits vary between runs. Every randomness-passed signal ends in exactly one bucket.

| Asset | signals | random decl. | max-open | cooldown | daily-loss | weekly-loss | min-lot refusal | entries |
|---|---|---|---|---|---|---|---|---|
| XAUUSD | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| GBPJPY | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| EURUSD | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## D. Performance Metrics (primary scenario)

| Asset | closed | win rate | PF | expectancy | avg win | avg loss | avg bars | max W. | max L. | DD | Sharpe | Sortino | exposure | return |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| XAUUSD | 0 | 0.00% | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0 | 0 | 0 | 0.000% | 0.000 | 0.000 | 0.00% | 0.00% |
| GBPJPY | 0 | 0.00% | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0 | 0 | 0 | 0.000% | 0.000 | 0.000 | 0.00% | 0.00% |
| EURUSD | 0 | 0.00% | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0 | 0 | 0 | 0.000% | 0.000 | 0.000 | 0.00% | 0.00% |

- Final capital per asset (primary scenario): XAUUSD: 20,000.00, GBPJPY: 20,000.00, EURUSD: 20,000.00 - unchanged with 0 trades.

## E. Trade Distribution

- Total trades across assets: 0
- **No trades in the primary scenario** (see section H for why).
- Long: 0 / Short: 0

### By exit reason

| Reason | Count |
|---|---|

### Sample trades per exit reason

| # | symbol | dir | entry time | entry px | exit time | exit px | lots | reason | PnL |
|---|---|---|---|---|---|---|---|---|---|

### By duration (candles held)

| Bucket | Count |
|---|---|
| 1-5 | 0 |
| 6-15 | 0 |
| 16+ | 0 |

### By entry hour (UTC)

| Hour | Count |
|---|---|

## F. Min-Lot Feasibility (deterministic)

Computed on the DETECTOR signal pool (independent of randomness): each signal's required lot size at the given capital, and the refusals a capital would force (`refusal%` = share of signals whose risk budget cannot cover a 0.01-lot position). This separates capital feasibility from entry randomness.

| Asset | signal pool | capital | signals | refusals | refusal % |
|---|---|---|---|---|---|
- No signals occurred, so no lot-size refusal is possible on this sample; the table is empty by construction.

Capital required to open a minimum 0.01-lot position, per asset, at observed detector-entry prices (n/a when the signal pool is empty):

| Asset | median price | capital for 0.01-lot (median) | 95th pct | worst price |
|---|---|---|---|---|
| XAUUSD | n/a | n/a | n/a | n/a |
| GBPJPY | n/a | n/a | n/a | n/a |
| EURUSD | n/a | n/a | n/a | n/a |

## G. Statistical Adequacy

- Data span: 2 years of real M15 history (2024-09-23 .. 2026-09-23, UTC) per asset.
- Detector signal pool sizes per asset: {'XAUUSD': 0, 'GBPJPY': 0, 'EURUSD': 0} - the binding constraint is the configured detector thresholds (see the reality check below), not the `entry_probability` filter.

| Asset | closed trades | minimum for adequacy | adequate? |
|---|---|---|---|
| XAUUSD | 0 | 30 | no (descriptive only) |
| GBPJPY | 0 | 30 | no (descriptive only) |
| EURUSD | 0 | 30 | no (descriptive only) |

Note: with few or zero trades per asset, win rate / PF / expectancy are descriptive only; no statistical claim about the strategy edge is made on this sample.

### Signal-pool reality check

The configured `drop_threshold = 3%` was NOT touched or re-optimised. On real 15-minute data over 2 years the detector pool is:

| Asset | bars >= 3% drop | bars >= 2x volume | **bars with BOTH** | max drop |
|---|---|---|---|---|
| XAUUSD | 1 | 3480 | **0** | 3.63% |
| GBPJPY | 0 | 2482 | **0** | 1.55% |
| EURUSD | 0 | 6204 | **0** | 1.01% |

- XAUUSD's single 3.6% bar fails `volume_multiplier` (observed 1.58x) and the reversal confirmation.
- The `drop >= 3%` AND `volume >= 2x` conjunction NEVER occurs, so the detector's first-stage preconditions are never met.

**0 detector signals is therefore the correct, faithful behaviour of the production pipeline at its configured thresholds, not a bug.** The strategy as configured is effectively dormant on these real M15 markets; organized randomness never gets to vote on an entry.

## H. Conclusion

- Pipeline mechanically valid on REAL data? **Yes** (data quality pass, detector runs, risk limits simulated, refusals transparently counted)
- Dataset real historical or synthetic? **Real** - broker M15 history
- Performance metrics preliminary or validated? **Not applicable** - the detector produced 0 signals at the configured thresholds, so there are no trades to measure on this instrument set
- Threshold calibration: `drop_threshold=3%` on 15-minute bars is 'catastrophe-searching' in name but effectively never fires on XAUUSD/GBPJPY/EURUSD M15 (see the reality check in G). This is reported as-is; thresholds were deliberately NOT optimised for this exercise.
- Risk-limit events simulated: max-open=0, cooldown=0, daily-loss=0, weekly-loss=0
- Ready for paper trading? **No** - a strategy that never triggers is not tradeable; calibration research is required before any paper run
- Ready for live trading? **No**
