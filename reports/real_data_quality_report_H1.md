# Phoenix Protocol - Real Historical Data Quality Report

> Source: MetaTrader 5 terminal export (real broker history, FBS-Demo). Server times converted to UTC using the empirically measured +3h server offset. This report is a data audit, not a performance claim.

| Symbol | TF | first (UTC) | last (UTC) | candles | span (days) | duplicates |
|---|---|---|---|---|---|---|
| XAUUSD | H1 | 2024-09-23 18:00:00+00:00 | 2026-09-23 17:00:00+00:00 | 11818 | 730.0 | 0 |
| GBPJPY | H1 | 2024-09-23 18:00:00+00:00 | 2026-09-23 17:00:00+00:00 | 12423 | 730.0 | 0 |
| EURUSD | H1 | 2024-09-23 18:00:00+00:00 | 2026-09-23 17:00:00+00:00 | 12423 | 730.0 | 0 |

## Missing / gap analysis

`missing_vs_span` = continuous 15-min slots minus present candles. Every missing slot must be explained by a measured gap (weekend week, daily broker break, or short anomaly); `unaccounted` is the leftover after removing ALL measured gaps and should be 0 for healthy data.

| Symbol | slots | bars | missing vs span | weekend | intraday | short | accounted | unaccounted |
|---|---|---|---|---|---|---|---|---|
| XAUUSD | 17520 | 11818 | 5702 | 5268 | 434 | 0 | 5702 | 0 |
| GBPJPY | 17520 | 12423 | 5097 | 5095 | 2 | 0 | 5097 | 0 |
| EURUSD | 17520 | 12423 | 5097 | 5095 | 2 | 0 | 5097 | 0 |

| Symbol | per-week Friday LAST bar (UTC) | per-week Sunday FIRST bar (UTC) | dominant intraday break hour | recurring? |
|---|---|---|---|---|
| XAUUSD | 20:00 | 22:00 | 22:00 | yes (22:00 UTC) |
| GBPJPY | 20:00 | 21:00 | 4:00 | none (continuous; only isolated 1-off gaps) |
| EURUSD | 20:00 | 21:00 | 4:00 | none (continuous; only isolated 1-off gaps) |

- Weekly shape sanity: EURUSD/GBPJPY open Sunday ~21:00 UTC and close Friday ~20:45-21:00 UTC; XAUUSD closes Sunday 22:00 UTC and clears a regular daily break ~22:00-23:15 UTC (institutional gold structure). The Sunday/Friday boundaries above match a fixed UTC+3 server offset; a systematic mismatch would mean the offset assumption is wrong.

## Row validity & volume

| Symbol | invalid OHLC | NaN OHLC | price<=0 | zero vol | negative vol | vol min | vol max |
|---|---|---|---|---|---|---|---|
| XAUUSD | 0 | 0 | 0 | 0 | 0 | 1 | 40660 |
| GBPJPY | 0 | 0 | 0 | 0 | 0 | 99 | 39904 |
| EURUSD | 0 | 0 | 0 | 0 | 0 | 55 | 25326 |

## Cleaning actions (as applied for backtesting)

Sources are never modified. The pipeline reads/cleans in memory.

| Symbol | duplicates kept-last | invalid rows dropped | unsorted fixed | final usable candles |
|---|---|---|---|---|
| XAUUSD | 0 | 0 | no | 11818 |
| GBPJPY | 0 | 0 | no | 12423 |
| EURUSD | 0 | 0 | no | 12423 |

## HTTPS evidence

- Timestamps: naive UTC (converted from server time, offset +3h measured directly against the terminal's newest M15 bar epoch).
- DST: server uses a fixed +3h offset (no DST); conversion is constant.
- Duplicates: deduplicated keep=last, then sorted ascending.

## Verdict

- DATA QUALITY: **PASS** all deviations from the continuous span are exactly accounted for by regular market breaks (weekend + daily close) and isolated one-off gaps.
