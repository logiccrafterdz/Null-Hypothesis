# Directional Bias - XAUUSD_M15_56202

Test: does the edge survive direction reversal / a passive long / random entry?

## 2A. Reversed direction (SHORT)

Identical entry conditions (close_near_high 0.7 / vol_ratio_prev 2.5 /
n_up_candles 8) and identical exit rules, mirrored for SHORT.

| metric | LONG (56202) | SHORT (mirror) |
|---|---:|---:|
| trades | 178 | 157 |
| win rate | 65.2% | 43.3% |
| profit factor | 1.73 | 0.52 |
| net return | +10.91% | -12.86% |
| max DD | 2.38% | 15.14% |
| sharpe (daily) | 1.26 | -1.70 |

Interpretation: **SHORT loses while LONG profits -> conditions merely ride the uptrend**

Over the same 24 months the mirrored SHORT version
LOST money.

## 2B. Buy-and-hold comparison

Buy-and-hold XAUUSD over the identical window (long at first close, hold to
last close):

| metric | 56202 (LONG strategy) | Buy-and-hold gold |
|---|---:|---:|
| return | +10.91% | +62.93% |
| sharpe (annualized, daily) | 1.26 | 1.01 |
| max drawdown | 2.38% | 27.79% |

- Return/maxDD: strategy 4.6 vs
  buy-and-hold 2.3.
- Mean trade duration 31 bars (7.7 h); cumulative
  position-hours = 11.6% of calendar time (up to 2 concurrent
  positions, so single-position exposure is roughly half of that).
- 56202 earned 10.9% while a passive long earned 62.9% - i.e. the strategy captured 17% of buy-and-hold's raw return, with max drawdown of 2.38% vs 27.79% for buy-and-hold.

The strategy's edge over buy-and-hold on absolute return, if any, is modest;
on drawdown it is dramatically better simply because it is only in the market
a fraction of the time and caps each losing trade at 2.5%.

## 2C. Random LONG baseline (500 strategies, same exits)

500 strategies with the **exact same exit rules / risk gates** but random
entry bars at density 0.0075 (identical to 56202's own signal count of
356/bars) - a "does entry timing matter?" control.

| stat | value |
|---|---:|
| random-LONG mean return | -4.22% |
| random-LONG median | -4.00% |
| random-LONG p5 / p95 | -12.62% / +4.67% |
| random-LONG min / max | -19.62% / +12.75% |
| % of random-LONGs profitable | 20.6% |
| **56202 percentile in random-LONG pool** | **99.8%** |

56202's +10.91% sits at the 99.8th percentile of
500 random LONG strategies with identical risk/exit math.
