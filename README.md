# Phoenix Protocol

An automated trading system. It trades things. Sometimes it makes money. Sometimes it doesn't.

## The Idea

Most trading systems try to predict the market. We don't. We wait until the market looks completely broken and then we enter. It's probably a terrible idea. The backtests say it works, but backtests always say things work.

## What It Does

- Detects when the market is having a really bad time
- Decides randomly whether to trade or not
- If it trades, it uses standard risk management
- If it doesn't, it waits for the next bad time

## Why "Phoenix Protocol"

Because we enter when everything is burning down and hope to rise from the ashes. Or something dramatic like that. The name was chosen by a random number generator.

## The Numbers

> **INVALID — superseded.** The figures below were produced by an earlier,
> buggy backtesting engine (exit orders were not actually executed, position
> sizing used the wrong units, the detector used hardcoded thresholds, and
> `weekday()==5` treated Saturday as Friday). They must NOT be quoted as
> strategy performance.

- Win rate: 72% **INVALID**
- Profit factor: 3.55 **INVALID**
- Max drawdown: -10.6% **INVALID**
- Total return: 30.66% **INVALID**

Corrected results for the current code are in
`reports/post_fix_backtest_report.md` (currently **PIPELINE VALIDATION ONLY**
on synthetic fixtures — not a real-market claim; see that report before
drawing any conclusion).

## How to Use

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Verify the fixing suite (all tests must pass)
python -m pytest tests/ -q

# 3. Real data (option A): export MT5 history to data/raw/
#    (server times converted to UTC; offset auto-documented in the CSV header)
python scripts/download_mt5_history.py --symbols XAUUSD GBPJPY EURUSD --days 730

# 3. Synthetic fixtures (option B): reproducible pipeline-validation data
#    (substitutes when MT5 is unavailable; NEVER treated as real history)
python scripts/generate_synthetic_data.py --symbols XAUUSD GBPJPY EURUSD --days 365

# 4. Run one asset through the corrected backtester
python main.py --mode backtest --asset XAUUSD --days 365

# 5. Generate the post-fix validation report
python scripts/generate_backtest_report.py --days 365 --capital 10000
```

If you want to actually use real money:
```bash
python main.py --mode live --assets XAUUSD GBPJPY
```

I wouldn't recommend the second option.

## What You Need

- Python 3.11+
- MetaTrader 5
- An MT5 account
- Poor judgment
- Willingness to lose money

## What It Trades

Forex and metals through MT5. No crypto. Crypto is for people who like unnecessary risk.

## Installation

Standard Python project setup. If you need instructions for this, you probably shouldn't be running trading bots.

## Disclaimer

This is experimental software. It might work. It might not. It might lose all your money. It might make money and then lose it all next week. I'm not responsible for any of that.

## License

MIT. Do whatever you want with it. It's probably not worth the effort anyway.

---

Built because someone said it couldn't be done.
