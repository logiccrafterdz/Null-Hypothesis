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

According to some simulations we ran:
- Win rate: 72% (probably won't hold up in real trading)
- Profit factor: 3.55 (seems suspiciously high)
- Max drawdown: -10.6% (sounds too good to be true)
- Total return: 30.66% (definitely won't be this good in practice)

> **Note:** These figures were produced by an earlier, buggy backtesting
> engine (exit orders were not actually executed, position sizing used the
> wrong units, and the detector used hardcoded thresholds). They are **not
> valid** until the backtest is re-run with the corrected code. Re-generate
> them with `python main.py --mode backtest --asset XAUUSD --days 365`
> after seeding local data with `python main.py --generate-sample-data`.

## How to Use

```bash
python main.py --mode backtest --asset XAUUSD --days 365
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
