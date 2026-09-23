# Research Candidate Backtests (Relaxed Bad-Luck Signals, Real Data)
## Methodology
- Entry mask = relaxed candidate only (drop AND volume screen; the same-bar reversal-pattern + ATR-spike stack of the production detector is NOT applied here - see the feasibility report for why it fires zero times on real data).
- Trade management mirrors production: stop 1.50%, TP 3.00%, trailing after 1.50% (distance 0.50%), max 15 bars, commission 0.02% per side, slippage 0.01%.
- Risk limits enabled (live mirror): daily 5%, weekly 10%, cooldown 3 trades after a loss, max 2 open positions. Minimum-lot sizing uses calculate_position_size.
- Randomness gate: seeded replica of the DecisionEngine rule (random < 0.6). Default capital 10000 for the equity run; refusals also reported for other capital scenarios.

## Summary (long entries, capital 10000, risk limits + randomness on)
| # | Sym | TF | drop | screen | signals | random-skip | size-refuse | entries | traded | win% | PF | avg/trade | ret% | maxDD% | success |
|---|-----|----|------|--------|---------|-------------|------------|---------|--------|------|----|-----------|------|--------|---------|
| 1 | GBPJPY | H1 | 0.0030 | ratio1.50 | 93 | 34 | 59 | 0 | 0 | 0.0% | 0.00 | 0.000% | 0.00% | 0.00% | no |
| 2 | XAUUSD | H1 | 0.0030 | ratio1.50 | 384 | 81 | 0 | 139 | 139 | 46.8% | 0.82 | -0.063% | -13.99% | 13.47% | no |
| 3 | XAUUSD | H1 | 0.0050 | ratio1.50 | 208 | 57 | 0 | 63 | 63 | 47.6% | 0.68 | -0.127% | -11.05% | 11.83% | no |
| 4 | EURUSD | M15 | 0.0020 | z2.00 | 89 | 18 | 0 | 29 | 29 | 44.8% | 0.97 | -0.004% | -0.91% | 2.01% | no |
| 5 | EURUSD | M15 | 0.0020 | ratio1.50 | 106 | 21 | 0 | 36 | 36 | 50.0% | 0.99 | 0.001% | -0.94% | 2.84% | no |
| 6 | GBPJPY | M15 | 0.0020 | z2.00 | 107 | 38 | 69 | 0 | 0 | 0.0% | 0.00 | 0.000% | 0.00% | 0.00% | no |
| 7 | GBPJPY | M15 | 0.0020 | ratio1.50 | 153 | 61 | 92 | 0 | 0 | 0.0% | 0.00 | 0.000% | 0.00% | 0.00% | no |
| 8 | XAUUSD | M15 | 0.0020 | z2.00 | 514 | 132 | 0 | 194 | 194 | 56.2% | 0.90 | -0.031% | -9.73% | 13.02% | no |
| 9 | XAUUSD | M15 | 0.0020 | ratio1.50 | 983 | 256 | 0 | 336 | 336 | 49.7% | 0.71 | -0.086% | -35.69% | 30.26% | no |
| 10 | EURUSD | M30 | 0.0025 | ratio2.00 | 55 | 13 | 0 | 12 | 12 | 8.3% | 0.07 | -0.292% | -4.78% | 4.48% | no |
| 11 | EURUSD | M30 | 0.0025 | ratio1.50 | 72 | 10 | 0 | 28 | 28 | 50.0% | 0.78 | -0.030% | -1.80% | 2.90% | no |
| 12 | GBPJPY | M30 | 0.0025 | z2.00 | 68 | 27 | 41 | 0 | 0 | 0.0% | 0.00 | 0.000% | 0.00% | 0.00% | no |
| 13 | GBPJPY | M30 | 0.0025 | ratio1.50 | 110 | 36 | 74 | 0 | 0 | 0.0% | 0.00 | 0.000% | 0.00% | 0.00% | no |
| 14 | XAUUSD | M30 | 0.0025 | z2.00 | 312 | 83 | 0 | 114 | 114 | 57.9% | 0.97 | -0.017% | -4.29% | 14.21% | no |
| 15 | XAUUSD | M30 | 0.0025 | ratio1.50 | 631 | 161 | 0 | 223 | 223 | 53.4% | 0.89 | -0.035% | -12.79% | 14.03% | no |

## Risk-gate refusals detail (capital 10000)
| # | Sym | TF | drop | screen | signals | max-open | cooldown | daily-loss | weekly-loss |
|---|-----|----|------|--------|---------|----------|----------|------------|-------------|
| 1 | GBPJPY | H1 | 0.0030 | ratio1.50 | 93 | 0 | 0 | 0 | 0 |
| 2 | XAUUSD | H1 | 0.0030 | ratio1.50 | 384 | 5 | 159 | 0 | 0 |
| 3 | XAUUSD | H1 | 0.0050 | ratio1.50 | 208 | 0 | 88 | 0 | 0 |
| 4 | EURUSD | M15 | 0.0020 | z2.00 | 89 | 0 | 42 | 0 | 0 |
| 5 | EURUSD | M15 | 0.0020 | ratio1.50 | 106 | 1 | 48 | 0 | 0 |
| 6 | GBPJPY | M15 | 0.0020 | z2.00 | 107 | 0 | 0 | 0 | 0 |
| 7 | GBPJPY | M15 | 0.0020 | ratio1.50 | 153 | 0 | 0 | 0 | 0 |
| 8 | XAUUSD | M15 | 0.0020 | z2.00 | 514 | 13 | 175 | 0 | 0 |
| 9 | XAUUSD | M15 | 0.0020 | ratio1.50 | 983 | 25 | 366 | 0 | 0 |
| 10 | EURUSD | M30 | 0.0025 | ratio2.00 | 55 | 0 | 30 | 0 | 0 |
| 11 | EURUSD | M30 | 0.0025 | ratio1.50 | 72 | 0 | 34 | 0 | 0 |
| 12 | GBPJPY | M30 | 0.0025 | z2.00 | 68 | 0 | 0 | 0 | 0 |
| 13 | GBPJPY | M30 | 0.0025 | ratio1.50 | 110 | 0 | 0 | 0 | 0 |
| 14 | XAUUSD | M30 | 0.0025 | z2.00 | 312 | 4 | 111 | 0 | 0 |
| 15 | XAUUSD | M30 | 0.0025 | ratio1.50 | 631 | 11 | 236 | 0 | 0 |

## Minimum-lot sizing refusals by capital scenario (same signal pools, always-on seeds)
Rate = would-be trades refused because the 2% risk budget cannot cover one 0.01 lot at the signal price.
| # | Sym | TF | drop | screen | 5000 | 10000 | 25000 | 50000 | 100000 |
|---|-----|----|------|--------|-----|-----|-----|-----|-----|
| 1 | GBPJPY | H1 | 0.0030 | ratio1.50 | 93/93 (100%) | 93/93 (100%) | 93/93 (100%) | 93/93 (100%) | 93/93 (100%) |
| 2 | XAUUSD | H1 | 0.0030 | ratio1.50 | 0/384 (0%) | 0/384 (0%) | 0/384 (0%) | 0/384 (0%) | 0/384 (0%) |
| 3 | XAUUSD | H1 | 0.0050 | ratio1.50 | 0/208 (0%) | 0/208 (0%) | 0/208 (0%) | 0/208 (0%) | 0/208 (0%) |
| 4 | EURUSD | M15 | 0.0020 | z2.00 | 0/89 (0%) | 0/89 (0%) | 0/89 (0%) | 0/89 (0%) | 0/89 (0%) |
| 5 | EURUSD | M15 | 0.0020 | ratio1.50 | 0/106 (0%) | 0/106 (0%) | 0/106 (0%) | 0/106 (0%) | 0/106 (0%) |
| 6 | GBPJPY | M15 | 0.0020 | z2.00 | 107/107 (100%) | 107/107 (100%) | 107/107 (100%) | 107/107 (100%) | 107/107 (100%) |
| 7 | GBPJPY | M15 | 0.0020 | ratio1.50 | 153/153 (100%) | 153/153 (100%) | 153/153 (100%) | 153/153 (100%) | 153/153 (100%) |
| 8 | XAUUSD | M15 | 0.0020 | z2.00 | 0/514 (0%) | 0/514 (0%) | 0/514 (0%) | 0/514 (0%) | 0/514 (0%) |
| 9 | XAUUSD | M15 | 0.0020 | ratio1.50 | 0/983 (0%) | 0/983 (0%) | 0/983 (0%) | 0/983 (0%) | 0/983 (0%) |
| 10 | EURUSD | M30 | 0.0025 | ratio2.00 | 0/55 (0%) | 0/55 (0%) | 0/55 (0%) | 0/55 (0%) | 0/55 (0%) |
| 11 | EURUSD | M30 | 0.0025 | ratio1.50 | 0/72 (0%) | 0/72 (0%) | 0/72 (0%) | 0/72 (0%) | 0/72 (0%) |
| 12 | GBPJPY | M30 | 0.0025 | z2.00 | 68/68 (100%) | 68/68 (100%) | 68/68 (100%) | 68/68 (100%) | 68/68 (100%) |
| 13 | GBPJPY | M30 | 0.0025 | ratio1.50 | 110/110 (100%) | 110/110 (100%) | 110/110 (100%) | 110/110 (100%) | 110/110 (100%) |
| 14 | XAUUSD | M30 | 0.0025 | z2.00 | 0/312 (0%) | 0/312 (0%) | 0/312 (0%) | 0/312 (0%) | 0/312 (0%) |
| 15 | XAUUSD | M30 | 0.0025 | ratio1.50 | 0/631 (0%) | 0/631 (0%) | 0/631 (0%) | 0/631 (0%) | 0/631 (0%) |

## Year 1 vs Year 2 (per-trade realised statistics)
The first calendar year in the sample is 2024-2025; the second is 2025-2026. Trade-level stats are shown because the sample is dominated by year-2 events for some assets.
| # | Sym | TF | drop | screen | Y1 n | Y1 win% | Y1 avg% | Y2 n | Y2 win% | Y2 avg% | Y1+Y2 ret$
|---|-----|----|------|--------|------|---------|---------|------|---------|---------|----------|
| 1 | GBPJPY | H1 | 0.0030 | ratio1.50 | 0 | 0.0% | 0.000% | 0 | 0.0% | 0.000% | 0 |
| 2 | XAUUSD | H1 | 0.0030 | ratio1.50 | 19 | 36.8% | -0.269% | 120 | 48.3% | -0.031% | -1112 |
| 3 | XAUUSD | H1 | 0.0050 | ratio1.50 | 8 | 75.0% | 0.032% | 55 | 43.6% | -0.150% | -970 |
| 4 | EURUSD | M15 | 0.0020 | z2.00 | 5 | 40.0% | -0.000% | 24 | 45.8% | -0.005% | -17 |
| 5 | EURUSD | M15 | 0.0020 | ratio1.50 | 7 | 28.6% | -0.293% | 29 | 55.2% | 0.073% | -3 |
| 6 | GBPJPY | M15 | 0.0020 | z2.00 | 0 | 0.0% | 0.000% | 0 | 0.0% | 0.000% | 0 |
| 7 | GBPJPY | M15 | 0.0020 | ratio1.50 | 0 | 0.0% | 0.000% | 0 | 0.0% | 0.000% | 0 |
| 8 | XAUUSD | M15 | 0.0020 | z2.00 | 16 | 50.0% | -0.073% | 178 | 56.7% | -0.027% | -555 |
| 9 | XAUUSD | M15 | 0.0020 | ratio1.50 | 31 | 38.7% | -0.117% | 305 | 50.8% | -0.083% | -2906 |
| 10 | EURUSD | M30 | 0.0025 | ratio2.00 | 3 | 33.3% | -0.427% | 9 | 0.0% | -0.247% | -448 |
| 11 | EURUSD | M30 | 0.0025 | ratio1.50 | 6 | 50.0% | -0.154% | 22 | 50.0% | 0.004% | -110 |
| 12 | GBPJPY | M30 | 0.0025 | z2.00 | 0 | 0.0% | 0.000% | 0 | 0.0% | 0.000% | 0 |
| 13 | GBPJPY | M30 | 0.0025 | ratio1.50 | 0 | 0.0% | 0.000% | 0 | 0.0% | 0.000% | 0 |
| 14 | XAUUSD | M30 | 0.0025 | z2.00 | 12 | 75.0% | 0.119% | 102 | 55.9% | -0.033% | -156 |
| 15 | XAUUSD | M30 | 0.0025 | ratio1.50 | 21 | 38.1% | -0.238% | 202 | 55.0% | -0.014% | -825 |

## Quarterly signal frequency (relaxed candidates)
| # | Sym | TF | drop | screen | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 |
|---|-----|----|------|--------|-----|-----|-----|-----|-----|-----|-----|-----|
| 1 | GBPJPY | H1 | 0.0030 | ratio1.50 | 1 | 25 | 23 | 9 | 7 | 5 | 10 | 4 |
| 2 | XAUUSD | H1 | 0.0030 | ratio1.50 | 2 | 43 | 37 | 58 | 26 | 58 | 60 | 55 |
| 3 | XAUUSD | H1 | 0.0050 | ratio1.50 | 2 | 14 | 14 | 37 | 11 | 38 | 37 | 34 |
| 4 | EURUSD | M15 | 0.0020 | z2.00 | 1 | 19 | 24 | 20 | 7 | 2 | 5 | 6 |
| 5 | EURUSD | M15 | 0.0020 | ratio1.50 | 1 | 21 | 27 | 29 | 9 | 2 | 7 | 5 |
| 6 | GBPJPY | M15 | 0.0020 | z2.00 | 3 | 24 | 25 | 12 | 8 | 3 | 10 | 10 |
| 7 | GBPJPY | M15 | 0.0020 | ratio1.50 | 3 | 32 | 45 | 18 | 10 | 5 | 11 | 11 |
| 8 | XAUUSD | M15 | 0.0020 | z2.00 | 2 | 44 | 31 | 80 | 40 | 91 | 83 | 82 |
| 9 | XAUUSD | M15 | 0.0020 | ratio1.50 | 7 | 76 | 60 | 162 | 55 | 143 | 165 | 178 |
| 10 | EURUSD | M30 | 0.0025 | ratio2.00 | 1 | 14 | 8 | 12 | 9 | 2 | 2 | 4 |
| 11 | EURUSD | M30 | 0.0025 | ratio1.50 | 1 | 14 | 10 | 24 | 10 | 2 | 4 | 4 |
| 12 | GBPJPY | M30 | 0.0025 | z2.00 | 2 | 17 | 15 | 7 | 4 | 3 | 8 | 5 |
| 13 | GBPJPY | M30 | 0.0025 | ratio1.50 | 4 | 29 | 29 | 10 | 5 | 6 | 11 | 8 |
| 14 | XAUUSD | M30 | 0.0025 | z2.00 | 2 | 31 | 22 | 48 | 26 | 56 | 53 | 40 |
| 15 | XAUUSD | M30 | 0.0025 | ratio1.50 | 7 | 59 | 48 | 102 | 51 | 90 | 109 | 90 |

## Exit reason distribution (top candidate per timeframe)

### EURUSD M15 drop=0.002 z2.0 (29 trades)
| reason | count | share | avg pnl% |
|--------|-------|-------|----------|
| MAX_DURATION_REACHED | 29 | 100.0% | -0.004% |

### EURUSD M30 drop=0.0025 ratio2.0 (12 trades)
| reason | count | share | avg pnl% |
|--------|-------|-------|----------|
| MAX_DURATION_REACHED | 11 | 91.7% | -0.180% |
| Stop Loss | 1 | 8.3% | -1.530% |

### XAUUSD H1 drop=0.003 ratio1.5 (139 trades)
| reason | count | share | avg pnl% |
|--------|-------|-------|----------|
| MAX_DURATION_REACHED | 103 | 74.1% | 0.169% |
| Stop Loss | 26 | 18.7% | -1.530% |
| Trailing Stop | 10 | 7.2% | 1.358% |
