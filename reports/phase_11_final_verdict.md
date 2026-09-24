# Phase 11 - Final Verdict

## Question

Is `XAUUSD_M15_56202` a genuinely exploitable alpha strategy, or a complex way of
buying gold in a bull market?

## Evidence summary

| test | result |
|---|---|
| A1 autopsy | momentum/strength-following LONG scalper (not capitulation) |
| A2 SHORT mirror | -12.86% (SHORT) vs +10.91% (LONG) |
| A2 buy-and-hold | gold +62.93% / sharpe 1.01 / DD 27.79% |
| A2 random-LONG pct | 99.8% (56202 in top 0.2th pct) |
| A3 regime | profits concentrated in uptrends |
| A4 forensics | WR 65.2%, skew -2.16, exits mixed |
| A5 WF1-OOS | +5.61% on 36 trades |
| A5 WF2-OOS | -0.84% on 21 trades |

## Interpretation

- SHORT mirror lost -12.9% while LONG made +10.9% -> profit is directionally dependent (long-only beta)
- gold B&H made +62.9% vs strategy +10.9% -> strategy did NOT beat simply holding gold; DD is lower only because position sizing is small

- Strategy return/maxDD = 4.6;
  buy-and-hold return/maxDD = 2.3.
- The strategy is LONG-only, enters only on strength, and was tested on a
  ~bullish gold tape
  (+62.93% buy-and-hold over the window).
- Its small max drawdown is largely a consequence of tiny position sizes
  (2% risk per trade) and short holding times, not of market timing skill.
- Fairness note: on a strict Sharpe basis (1.26 vs 1.01) the strategy looks
  'better' than buy-and-hold, but that is an artefact of expressing a ~12%
  exposure (2% risk per trade, ~12% cumulative position
  hours) against an annualising denominator. It never deployed capital at
  buy-and-hold scale. Levering it up to B&H-like exposure would scale its
  drawdowns too - and those drawdowns cluster exactly when gold falls, the
  same risk a passive long already carries.

## VERDICT: B - DIRECTIONAL BETA

LONG-only profile. SHORT mirror -12.9% vs LONG +10.9%. Passive long gold +62.9% out-earned the strategy (+10.9%), and the only losing quarter (Q7, gold -12.2%) plus the negative WF2-OOS window both coincide with gold declines. Entry timing does beat random LONG entries (99.8th percentile) - but that timing skill exists ONLY on the long side of a rising instrument: it is long-beta capture, not market-neutral alpha.

### Recommendation

- **VERDICT B** - 
  DO NOT treat this as an alpha strategy or deploy as such. Its edge is largely a gold-bull-market beta artifact. Do NOT proceed to paper trading unless relabelled as a simple long-beta sleeve with expectations pegged to gold exposure, not to alpha.
  
  

> Phase 11 forensic methodology: verbose sim reproduced Phase-10 recorded
> metrics exactly (trades 178, ret 10.912%,
> PF 1.7263, DD 2.384%,
> sharpe 1.2581).
> Generated 2026-09-24 19:33 UTC.
