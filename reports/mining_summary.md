# Mining Session Summary - Chaos Discovery Engine

- Generated: 2026-09-24T19:01:11+00:00
- Assets: XAUUSD, EURUSD
- Quota per asset: 2000
- Luck baseline per asset: 800
- Seed: 2026

## Backtester validation (reference reproduction)

| Asset | Signals | Executed (0.6 gate) | Return (ref) | Engine trades | Engine ret | Matches report | Engine == ref sim |
|---|---:|---:|---:|---:|---:|:---:|:---:|
| XAUUSD | 983 | 336 | -35.69% | 487 | -36.05% | yes | yes |
| EURUSD | 106 | 36 | -0.94% | 45 | -3.96% | yes | yes |

## Per-asset funnel

| Asset | Generated | Luck baseline (mean / p95) | Primary filter | Robustness | FDR + p95 | Top N |
|---|---:|---:|---:|---:|---:|---:|
| XAUUSD | 2000 | 800 (-15.1% / 6.5%) | 3 | 2 | 2 | 2 |
| EURUSD | 2000 | 800 (-18.2% / -5.5%) | 0 | 0 | 0 | 0 |
