# Autopsy - XAUUSD_M15_56202

- Strategy ID: `XAUUSD_M15_56202` | Direction: LONG | Asset: XAUUSD | TF: M15
- Data window: 2024-09-23 17:15:00+00:00 -> 2026-09-23 17:00:00+00:00 (47,231 bars, ~24 months)
- Source: Chaos Discovery Engine (Phase 10), seed 2026, quota 2000/asset.

## 1. Entry specification

Operator: `mixed` (mixed = `(A) and (B)` where A and B
are each OR-groups)

| # | type | params | meaning |
|---|---|---|---|
| 1 | `close_near_high` | `{"x": 0.7}` | Close in top 0.7 of the bar range |
| 2 | `vol_ratio_prev` | `{"x": 2.5}` | Volume > 2.5x the mean of the previous 20 bars (production detector formula) |
| 3 | `n_up_candles` | `{"n": 8}` | 8 consecutive rising closes |

Mixed structure (group of 1 / group of 2):
- LEFT  (OR): `close_near_high`
- RIGHT (OR): `vol_ratio_prev`, `n_up_candles`
- Entry mask = LEFT **AND** RIGHT.

## 2. Exit specification

| rule | value |
|---|---|
| stop_loss_pct | 0.025 (-2.5%) |
| take_profit_pct | 0.005 (+0.5%) |
| trailing | True (activation 0.005, distance 0.005) |
| max_duration_bars | 45 (11.25 h) |

Risk: 2% of equity per trade, max 2 concurrent
positions, commission 0.0002, slippage 0.0001.

Closed-exit reasons observed: MAX_DURATION_REACHED x86, Stop Loss x2, Take Profit x85, Trailing Stop x5.

## 3. Plain-language description

This strategy enters a LONG position when the current M15 bar meets **EITHER** [close in the top 70% of its own bar range] OR ... no - specifically: `mixed` splits the 3 conditions as (`Close in top 0.7 of the bar range`) OR'd together, then AND'd with (`Volume > 2.5x the mean of the previous 20 bars (production detector formula)`, `8 consecutive rising closes`) OR'd together. So it buys when a bar closes near its own range high while (volume is > 2.5x its 20-bar trailing mean OR 8 consecutive rising closes have just printed). It exits on stop-loss (-2.5%), take-profit (+0.5%), a trailing stop that activates at +0.5% and ratchets at 0.5% below the peak close, or after 45 bars (11.25 h), whichever comes first. Position size = 2% of equity risked on the -2.5% stop, max 2 concurrent positions, 5%/10% daily/weekly loss caps, 3-trade cooldown after a losing close.

## 4. Economic / market-logic interpretation

- `close_near_high (0.7)` is textbook **buying strength**: the bar closed
  within the top 70% of its range, i.e. buyers controlled the close. This is
  a momentum/continuation signal, not a capitulation signal.
- `vol_ratio_prev (2.5)` = participation spike (production detector formula,
  20-bar trailing mean, current bar excluded). When it coincides with an
  up-close, it says "institutional participation on the buy side".
- `n_up_candles (8)` = 2 hours of unbroken rising closes - trend momentum.
- The whole entry condition therefore describes **trend/momentum strength in
  an already rising market**, NOT a reversal setup. The system's stated
  philosophy is buying capitulation; this survivor does the opposite - it
  chases strength.
- Exits are a **tight-profit grinder**: target +0.5% with a fast trailing
  activation at +0.5% and a wide -2.5% stop. It collects many small wins
  when momentum persists and caps each loser at 2.5%.
- Plausible institutional explanation: it is a trend-following / breakout
  scalper that only ever goes LONG. On an instrument given a strong positive
  drift (gold 2024-09 -> 2026-09), that profile will accumulate small
  positive expectancy even without genuine reversal skill. The 65% win rate
  is the signature of the tight +0.5% target, not of market timing.
