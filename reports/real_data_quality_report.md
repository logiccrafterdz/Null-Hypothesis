# Phoenix Protocol - Real Historical Data Quality Report

> Source: MetaTrader 5 terminal export (real broker history, FBS-Demo). Server times converted to UTC using the empirically measured +3h server offset. This report is a data audit, not a performance claim.

| Symbol | TF | first (UTC) | last (UTC) | candles | span (days) | duplicates |
|---|---|---|---|---|---|---|
| XAUUSD | M15 | 2024-09-23 17:15:00+00:00 | 2026-09-23 17:00:00+00:00 | 47231 | 730.0 | 0 |
| GBPJPY | M15 | 2024-09-23 17:15:00+00:00 | 2026-09-23 17:00:00+00:00 | 49679 | 730.0 | 0 |
| EURUSD | M15 | 2024-09-23 17:15:00+00:00 | 2026-09-23 17:00:00+00:00 | 49680 | 730.0 | 0 |

## Missing / gap analysis

`missing_vs_span` = continuous 15-min slots minus present candles. Every missing slot must be explained by a measured gap (weekend week, daily broker break, or short anomaly); `unaccounted` is the leftover after removing ALL measured gaps and should be 0 for healthy data.

| Symbol | slots | bars | missing vs span | weekend | intraday | short | accounted | unaccounted |
|---|---|---|---|---|---|---|---|---|
| XAUUSD | 70080 | 47231 | 22849 | 21083 | 1765 | 1 | 22849 | 0 |
| GBPJPY | 70080 | 49679 | 20401 | 20383 | 15 | 3 | 20401 | 0 |
| EURUSD | 70080 | 49680 | 20400 | 20383 | 15 | 2 | 20400 | 0 |

| Symbol | per-week Friday LAST bar (UTC) | per-week Sunday FIRST bar (UTC) | dominant intraday break hour | recurring? |
|---|---|---|---|---|
| XAUUSD | 20:00 | 22:00 | 22:00 | yes (22:00 UTC) |
| GBPJPY | 20:00 | 21:00 | 8:00 | none (continuous; only isolated 1-off gaps) |
| EURUSD | 20:00 | 21:00 | 8:00 | none (continuous; only isolated 1-off gaps) |

- Weekly shape sanity: EURUSD/GBPJPY open Sunday ~21:00 UTC and close Friday ~20:45-21:00 UTC; XAUUSD closes Sunday 22:00 UTC and clears a regular daily break ~22:00-23:15 UTC (institutional gold structure). The Sunday/Friday boundaries above match a fixed UTC+3 server offset; a systematic mismatch would mean the offset assumption is wrong.

## Row validity & volume

| Symbol | invalid OHLC | NaN OHLC | price<=0 | zero vol | negative vol | vol min | vol max |
|---|---|---|---|---|---|---|---|
| XAUUSD | 0 | 0 | 0 | 0 | 0 | 1 | 10926 |
| GBPJPY | 0 | 0 | 0 | 0 | 0 | 8 | 10339 |
| EURUSD | 0 | 0 | 0 | 0 | 0 | 6 | 7703 |

## Cleaning actions (as applied for backtesting)

Sources are never modified. The pipeline reads/cleans in memory.

| Symbol | duplicates kept-last | invalid rows dropped | unsorted fixed | final usable candles |
|---|---|---|---|---|
| XAUUSD | 0 | 0 | no | 47231 |
| GBPJPY | 0 | 0 | no | 49679 |
| EURUSD | 0 | 0 | no | 49680 |

## HTTPS evidence

- Timestamps: naive UTC (converted from server time, offset +3h measured directly against the terminal's newest M15 bar epoch).
- DST: server uses a fixed +3h offset (no DST); conversion is constant.
- Duplicates: deduplicated keep=last, then sorted ascending.

## Verdict

- DATA QUALITY: **PASS** all deviations from the continuous span are exactly accounted for by regular market breaks (weekend + daily close) and isolated one-off gaps.
