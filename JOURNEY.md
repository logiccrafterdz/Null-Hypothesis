# Null Hypothesis: The Journey

## A Quant Research Engine for Testing Intraday Alpha

> We set out to find alpha. We found the truth instead.
> And the truth is more valuable.

---

### Prologue: The Question

Every retail trading system on the internet is a lie. That is the uncomfortable
premise that this project started from. The claim is almost always the same:
a clever indicator, a secret entry rule, a backtest with a 72% win rate, a
"PROVEN" strategy that only needs your attention (and your deposit) to print
money.

Most of those systems are either accidental curve-fits or deliberate scams.
They trade synthetic curves in one direction while the broker trades the
spread in the other. The question this project set out to answer was simple
and brutal:

> **Can a systematically designed, rigorously tested, statistically honest
> trading strategy produce a real, out-of-sample edge on real market data?**

Not "can we paint a pretty equity curve." Not "can we write a backtest that
looks amazing." The question was whether **any** reproducible edge survives
contact with the actual market.

The original thesis was romantic: a strategy called "Lucky Loser" — later
"Phoenix Protocol" — that would wait for the market to capitulate (a "Bad Luck
Moment") and then enter at the moment of maximum apparent loss probability,
because that is precisely when reversal probability peaks. Add "organized
randomness" to avoid institutional algorithm detection. It was a beautiful
idea. This document is the story of what happened when we tested it.

It is the story of an eleven-phase scientific journey that ended with a
different, more valuable discovery than the one we set out to make.

---

### Chapter 1: Building the Machine (Phases 1-6)

We did not start with a hypothesis and a prayer. We built a production-grade
trading system first, with the discipline of an engineering team that
intended to put real capital behind it.

The architecture was modular and honest by design:

- **Data Fetcher** (`src/core/data_fetcher.py`) — multi-source data
  fetching with caching, MT5 integration, resampling for multiple timeframes.
- **Market Analyzer** (`src/core/market_analyzer.py`) — the "Bad Luck Detector";
  the heart of the original idea. It looked for the signature of capitulation:
  price drop, volume spike, volatility spike, and reversal pattern.
- **Decision Engine** (`src/core/decision_engine.py`) — the "organized
  randomness" component, powered by a cryptographic RNG. Uncertainty by
  design.
- **Risk Manager** (`src/core/risk_manager.py`) — position sizing, daily and
  weekly loss limits, correlation checks, cooldowns after losses.
- **Trade Executor** (`src/core/trade_executor.py`) — order placement,
  position monitoring, trailing stops, the full trade lifecycle.
- **Unified Broker Interface** (`src/api/broker_interface.py`) — a clean
  abstraction so any broker could be plugged in without touching strategy
  logic.

The strategy itself (`BadLuckStrategy`) watched for a specific set of
conditions: a large price drop on a 15-minute bar, a volume spike, a
volatility spike, a reversal pattern — five gates that all had to fire
together. When they did, the random decision engine decided whether to enter.

Then came the audit. A structured audit scored the system **92/100** and,
crucially, found critical bugs — including one that treated Saturday as Friday
(`weekday() == 5`) and another where exit orders were never actually executed
in the backtester. These bugs were found precisely because the audit demanded
evidence rather than assertion. They were fixed, the tests were expanded, and
the system reached a state where **122 tests passed** — a production-grade,
defensible codebase.

We thought we were ready. We were catastrophically wrong, in the most useful
way possible.

---

### Chapter 2: The Reality Check (Phase 7)

The moment of truth arrived with real market data: **two years of actual FBS
MT5 broker history** for XAUUSD, GBPJPY, and EURUSD on M15 timeframes. This was
the first time the engine had ever seen the real thing.

The discovery was shocking and immediate: **the detector never fired. Zero
signals. Not once in two years.**

Let that sink in. The entire "Bad Luck Moment" thesis — a 3% drop on M15 — does
not exist on these instruments. The 99th percentile of real 15-minute drops on
EURUSD is **0.16%**. On GBPJPY it is **0.20%**. On XAUUSD, the most volatile
of the three, it is **0.59%**. The single largest 15-minute drop recorded in
two years of XAUUSD data was **3.6% — and it happened exactly once.**

Combined with the volume and volatility conditions, the number of complete
signals over two years was **zero**. The strategy, as configured, was
behaviourally identical to no strategy at all. All that sophisticated
engineering — the random decision engine, the risk gates, the news filters —
was consulted exactly never.

There is a lesson here that cost us almost nothing and would have cost a naive
trader everything: **backtests on synthetic data can lie.** The earlier Phase-6
backtests on synthetic fixtures had painted a picture of a working system. The
fixtures were deterministic, well-behaved, and wrong. Synthetic data cannot
tell you whether your threshold is realistic, because your threshold *defined*
the synthetic data.

### Chapter 3: Calibration Attempts (Phase 8)

So the original configuration was dead. The scientific response was not to
abandon the project, but to ask the next question properly:

> **Are there any threshold/timeframe combinations on real data where the
> capitulation idea produces signals — and, more importantly, an edge?**

We ran a full signal-feasibility study. Relaxed thresholds *do* produce
signals: XAUUSD M15 with a 0.2% drop and 1.5x volume gives 983 signals in two
years; M30 gives 631; H1 gives 384. Dynamic trailing-percentile thresholds
produce steady signal pools without any fixed hard threshold. So frequency
was solved.

But **profitability was not.** Forward closed-bar returns for every
shortlisted candidate were statistically indistinguishable from an
identically-sized random baseline. Mean edges ranged from roughly -0.2% to
+0.2% — mostly negative or within one standard error of zero. No configuration
was positive in both year-one and year-two. When we applied the full
production trade management (stop, take-profit, trailing, time limit), every
realised simulation **lost money**: XAUUSD from -4.3% to -35.7%, EURUSD from
-0.9% to -4.8%, with profit factors of 0.07 to 0.99 against the 2.0 success
bar.

There was also a structural discovery about GBPJPY: it is **untradeable for
small accounts**. At 2% risk and a 1.5% stop with its contract size, a single
0.01-lot position requires about **$127,000** of capital. Even at a $100k
account size, the broker refused 100% of signals on minimum-lot grounds. This
is not a parameter problem; it is a structural property of the instrument.

The Phase-8 verdict was a flat, unambiguous **NO-GO**.

Note what did *not* happen: we did not lower the success bar to "slightly
better than losing." We did not curve-fit a threshold because it backtested
well. The study explicitly documented its own guardrails: every candidate was
pre-fixed on grids, synthetic data was never used as evidence, and no
production configuration was touched.

### Chapter 4: The Pivot (Phase 9)

The capitulation premise had one more life in it. The detector had required a
drop AND a reversal pattern on the *same* bar — but reversal patterns (which
appear on ~27% of bars) are structurally incompatible with large-drop bars
(which have patterns on only ~1% of them). What if we restructured the idea?

Phase 9 tested two pivots:

1. **Next-Bar Reversal** — enter on the bar *after* capitulation, which makes
   the no-lookahead structure correct.
2. **Panic Continuation** — instead of fading the capitulation, bet that the
   panic continues.

Both were tested with the same rigor: real data, no-lookahead splits,
production trade management. **Both failed.** No edge. The market kept its
secrets.

This was the point where a lesser project would have started lying to itself.
We had now spent three phases proving, with escalating rigor, that the original
idea does not work. But the research engine was getting *better* with each
failure. The failures weren't wasted; they were data points.

### Chapter 5: Chaos Theory (Phase 10)

Here is where the project made its biggest philosophical leap. If human logic
kept failing, abandon human logic. Stop designing strategies with the mind
and start testing strategy *space* itself.

We built a **Random Hypothesis Mining** engine — a Chaos Discovery Engine.
Instead of writing one clever strategy, we generated thousands of random ones
from a library of **50+ atomic conditions** (price relationships, volume
states, candle patterns, volatility regimes) composed into random logical
structures. Then we subjected them to the most brutal statistical gauntlet we
could build:

1. **Backtester validation first** — the mining engine had to exactly
   reproduce the Phase-8 reference results before it was allowed to mine
   anything.
2. **Luck baseline** — 800 random-entry strategies per asset to establish
   exactly what "unskilled" looks like (institutional-grade baseline, not a
   coin flip).
3. **Primary filter** — reject anything that does not beat the luck baseline
   by the primary success criteria.
4. **Robustness** — only strategies that remain positive when the edges are
   stressed get through.
5. **FDR correction (Benjamini-Hochberg)** — because if you test 2,000
   strategies, you will get false positives by pure chance, and the false
   discovery rate must be controlled. Combined with a p95 luck-percentile
   requirement.

The funnel for XAUUSD:
> **2,000 generated → 3 primary → 2 robustness → 2 FDR+p95 → 2 top N**

The funnel for EURUSD:
> **2,000 generated → 0. ZERO.** Not one strategy survived even the first
> filter. No candidate survived the tested discovery pipeline on EURUSD —
> not even a false positive made it through FDR correction.

Under the tested search space, EURUSD yielded nothing at all — not one
candidate passed the discovery pipeline. XAUUSD yielded two survivors — both
LONG-only strategies on a rising asset.

The two survivors in the XAUUSD top list:

| id | Direction | Trades | Win% | PF | Return% | MaxDD% | Sharpe | p(luck) | Composite |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| XAUUSD_M15_56202 | LONG | 178 | 65.2 | 1.73 | 10.9 | 2.4 | 1.26 | 0.0275 | 105.2 |
| XAUUSD_M15_28590 | LONG | 224 | 50.0 | 1.33 | 12.5 | 10.6 | 0.55 | 0.0238 | 53.8 |

That p(luck) of 0.0275 on the leader means the probability its performance is
pure luck is less than 3%. Statistically, it survived everything. And yet…

### Chapter 6: The Autopsy (Phase 11)

A strategy can pass every statistical filter and still be worthless — if what
it is actually capturing is not "edge" but **exposure**. Phase 11 was the
forensic autopsy that asked the final question:

> **Is XAUUSD_M15_56202 genuine, market-neutral alpha, or is it a complex way
> of buying gold in a bull market?**

The forensic toolkit was designed to be impossible to argue with: a verbose
simulator that had to reproduce the Phase-10 recorded metrics *exactly*
(trades, return, profit factor, max drawdown, Sharpe) before any conclusion
was trusted. It passed. Then we ran the experiments.

**The SHORT mirror test.** Take the identical entry conditions, mirror them
for short trades. If the strategy has real alpha, it should work in both
directions or at least not collapse. The LONG version made **+10.91%**. The
SHORT mirror lost **-12.86%** (157 trades, 43.3% win rate, 0.52 profit
factor). A strategy that loses money when reversed is not capturing an
exploitable pattern — it is riding a direction.

**The buy-and-hold comparison.** Ten intentionally simple dollars. Buy gold
at the start, hold for the full two years. Result: **+62.93%**. The strategy's
sophisticated 178-trade journey made **+10.91%**. The strategy captured
roughly 17% of what a passive, brainless, always-in-the-market long position
made — with lower drawdown only because its position sizes were tiny and its
holding times short. The market paid us for being long, not for being clever.

**The random control.** We simulated 500 random LONG strategies with the same
exit rules and signal density, and placed 56202 inside that distribution. It
sits at the **99.8th percentile** — its entry timing beats random long
entries. But that "timing skill" exists *only on the long side of a rising
instrument*. That is the definition of directional beta: you are good at
knowing when to be long in a bull market. That is not the same as alpha.

**The regime analysis.** Profits are concentrated in STRONG UP quarters. The
single losing quarter (Q7) is the one where gold itself fell -12.22%. The
correlation between monthly strategy returns and monthly gold returns
is **+0.43**.

**The walk-forward collapse.** Fold 1 out-of-sample is beautiful: +5.61% on
36 trades, 77.8% win rate, 2.97 profit factor. Fold 2 out-of-sample is
**-0.84%** — and it lands exactly on the period when gold slid. The negative
out-of-sample window is not a statistical accident; it is the signature of
directional beta. When the thing you are secretly long of falls, you lose.

**The trade forensics.** The famous "65.2% win rate" turned out to be an
illusion of construction. A tight +0.5% take-profit clips 85 trades at a fixed
+0.47% win (100% wins). Meanwhile 86 trades timed out at maximum duration
(48% of the book) with a 31% win rate and a -11.5% contribution. Two stop-loss
exits cost more in dollars than 20 take-profit wins earned. Skewness is -2.16
(fat left tail), kurtosis +7.41. Remove the best 5 trades and the strategy
shrinks to +11.19% gross of entry commissions. The headline win rate is a
presentation artifact, not an edge.

**The verdict: B — DIRECTIONAL BETA.**

Not A (genuine alpha). Not D (a false positive — it genuinely beat random
long entry). It is B: a long-only strategy on a bull asset whose every "edge"
turns out to be leverage into a rising market, noisily but statistically
honestly exposed.

---

### Epilogue: What We Learned

The final truth of this project is worth far more than a working strategy
would have been:

1. **No exploitable M15 alpha was detected under the tested search space.** A
   two-year, four-thousand strategy search across two major liquid instruments
   found exactly **zero** exploitable intraday M15 alpha.

2. **Most "strategies" sold commercially are disguised beta.** Ours was. We
   only found out because we did the SHORT mirror test and the buy-and-hold
   comparison — two experiments that almost nobody in the retail space ever
   runs. A 65% win rate with a Sharpe of 1.26 is not alpha if gold went up
   62.9% while you were in it.

3. **Random mining + statistical correction is the only honest method.**
   Chance is not a threat to be eliminated; it is a background to be measured.
   Mine thousands of hypotheses, compare them to a true luck baseline, correct
   for the false discovery rate, then autopsy the survivors. This is how
   science should be done with markets.

4. **A truthful NO-GO is worth more than a deceptive YES.** Three flat NO-GOs
   and one directional-BETA diagnosis saved us — and anyone who used this
   engine — from the inevitable drawdown of deploying a disguised-beta strategy
   at scale in a market regime change.

5. **The engine is the real achievement.** What survived the journey is not a
   strategy. It is a **scientific research instrument** that runs 133+
   tests, ingests real broker data, generates and backtests thousands of
   random hypotheses, controls false discovery rates, and dissects survivors
   forensically. That engine can test ANY future hypothesis honestly — and was
   itself only made trustworthy by this journey of proving hypotheses wrong.

The null hypothesis — "no exploitable edge exists under the tested methods" —
was stated, tested, and stressed by its own engine, and it was **not rejected**.
That is not failure. That is the rarest thing in quantitative trading: a
definitive, reproducible, honest answer.

We set out to find alpha. We found the truth instead. The truth is worth more.

---

### Appendix: Technical Specifications

**Architecture**

- `src/core/` — data_fetcher, market_analyzer, decision_engine, risk_manager,
  trade_executor
- `src/strategies/` — BaseStrategy + filters (trend, volatility, news)
- `src/api/` — broker_interface, mt5_connector
- `src/utils/` — indicators, logger, helpers, notifications
- `backtesting/` — backtester, monte_carlo, walk_forward
- `scripts/` — data collection, reporting, mining, forensics
- `dashboard/` — Streamlit visualization
- `config/` — settings, strategy parameters, credentials, research candidates

**Test suite**: 133 passing tests across unit, integration, and mining
validation (plus one documented pre-existing parity failure). Coverage spans
indicators, the backtester, the mining engine, risk management, brokers, and
end-to-end workflows.

**Data pipeline**: real FBS MT5 broker history, UTC-normalized, automated
import and quality validation. Research distinguishes strictly between real
data (evidence) and synthetic fixtures (pipeline verification only).

**Statistical methods**: false discovery rate correction (Benjamini-Hochberg),
Monte Carlo luck baselines, percentile rankings, p(luck) estimation, walk-
forward out-of-sample validation, SHORT-mirror and buy-and-hold controls,
distribution shape analysis (skew/kurtosis), and robustness stress testing.

---

*This document is the honest record of an honest project. Every number in it
can be reproduced from the code and reports in this repository.*