"""
Export historical OHLCV from MetaTrader 5 to CSV.

Phase 2 Option A of the post-fix validation bootstrap: pulls real broker
history so local backtests can run reproducibly with production-grade data.

This script runs ONCE on a machine with an MT5 terminal installed and
logged in. It writes historical fixtures only; it never places trades and
is never invoked during automated tests (tests mock the broker).

Usage
-----
    python scripts/export_mt5_history.py --symbol XAUUSD --days 730
    python scripts/export_mt5_history.py --symbol XAUUSD GBPJPY EURUSD --days 365
    python scripts/export_mt5_history.py --symbol XAUUSD --timeframe M15 --days 365 --output data/raw

Output
------
    data/raw/{symbol}_{timeframe}.csv

Columns:
    datetime, open, high, low, close, volume

Timezone handling:
    MetaTrader 5 returns server-local wall-clock times. They are written
    unchanged and documented in a CSV header comment; they are NOT auto-
    converted to UTC. The backtest pipeline interprets naive timestamps as
    UTC for session/date filtering (see src/core/data_fetcher.py).
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


DEFAULT_SYMBOLS = ["XAUUSD", "GBPJPY", "EURUSD"]

TIMEFRAME_LABELS = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}

MINUTES_PER_BAR = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "D1": 1440,
}


def export_symbol(
    mt5,
    symbol: str,
    timeframe: str,
    utc_from: datetime,
    utc_to: datetime,
    output_path: Path,
) -> int:
    """Download one symbol's history and write it to a CSV file."""
    tf_attr = TIMEFRAME_LABELS[timeframe]
    tf = getattr(mt5, tf_attr)

    if not mt5.symbol_select(symbol, True):
        print(f"ERROR: cannot select symbol '{symbol}': {mt5.last_error()}", file=sys.stderr)
        return 1

    rates = mt5.copy_rates_range(symbol, tf, utc_from, utc_to)
    if rates is None or len(rates) == 0:
        print(
            f"ERROR: no historical data for {symbol} {timeframe} "
            f"({utc_from:%Y-%m-%d} to {utc_to:%Y-%m-%d}): {mt5.last_error()}",
            file=sys.stderr,
        )
        return 1

    df = pd.DataFrame(rates)
    # MT5 epoch timestamps are server-local wall-clock times; keep them as-is.
    df["datetime"] = pd.to_datetime(df["time"], unit="s")
    df = df[["datetime", "open", "high", "low", "close", "volume"]].copy()
    df.drop_duplicates(subset="datetime", keep="last", inplace=True)
    df.sort_values("datetime", inplace=True)

    header = [
        "# source: MetaTrader5 export (scripts/export_mt5_history.py)",
        f"# symbol: {symbol}",
        f"# timeframe: {timeframe}",
        f"# first_bar: {df['datetime'].iloc[0]:%Y-%m-%d %H:%M:%S}",
        f"# last_bar: {df['datetime'].iloc[-1]:%Y-%m-%d %H:%M:%S}",
        "# timezone: MT5 server local time (NOT converted to UTC)",
        "# columns: datetime, open, high, low, close, volume",
    ]
    with output_path.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(header) + "\n")
        df.to_csv(fh, index=False)

    print(f"Exported {len(df)} bars for {symbol} {timeframe} -> {output_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export MT5 historical OHLCV for local backtests."
    )
    parser.add_argument("--symbol", nargs="+", default=DEFAULT_SYMBOLS,
                        help="Symbol(s) to export (default: XAUUSD GBPJPY EURUSD)")
    parser.add_argument("--timeframe", default="M15", choices=list(TIMEFRAME_LABELS),
                        help="Bar timeframe (default: M15)")
    parser.add_argument("--days", type=int, default=730,
                        help="Days of history to request (default: 730)")
    parser.add_argument("--output", default=str(Path(__file__).parent.parent / "data" / "raw"),
                        help="Output file or directory (default: data/raw)")
    args = parser.parse_args()

    try:
        import MetaTrader5 as mt5
    except ImportError as e:
        print(
            "ERROR: MetaTrader5 package is not installed.\n"
            "Install it with:  pip install MetaTrader5\n"
            "This is required only for real-history export; you can use\n"
            "    python scripts/generate_synthetic_data.py\n"
            "for pipeline validation without MT5.",
            file=sys.stderr,
        )
        return 1

    if not mt5.initialize():
        print(
            "ERROR: MetaTrader 5 terminal is not running or not logged in.\n"
            "Start the MT5 terminal, log in to your broker account, then retry.\n"
            f"initialize() returned: {mt5.last_error()}",
            file=sys.stderr,
        )
        return 1

    try:
        now = datetime.now()
        utc_to = now
        utc_from = now - timedelta(days=args.days)

        output = Path(args.output)
        if output.suffix.lower() == ".csv":
            # Single-file mode: only meaningful for one symbol.
            if len(args.symbol) != 1:
                print("ERROR: --output as a .csv file requires exactly one --symbol.",
                      file=sys.stderr)
                return 1
            targets = {args.symbol[0]: output}
        else:
            output.mkdir(parents=True, exist_ok=True)
            targets = {
                sym: output / f"{sym}_{args.timeframe}.csv"
                for sym in args.symbol
            }

        rc = 0
        for symbol, csv_path in targets.items():
            rc += export_symbol(mt5, symbol, args.timeframe, utc_from, utc_to, csv_path)
        return rc
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())