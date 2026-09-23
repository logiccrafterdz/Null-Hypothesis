"""
Download real M15 OHLCV history from a MetaTrader 5 terminal into data/raw.

REAL MARKET DATA ACQUISITION (Phase 7 of the honest validation package).

This script is meant to run ONCE on a machine with a MetaTrader 5 terminal
that is INSTALLED, RUNNING and LOGGED IN to a broker account (e.g. FBS).
It only downloads historical candles; it never places trades and is never
invoked by the automated test suite (tests mock the broker).

Requirements / failure modes
----------------------------
- MetaTrader5 package missing       -> clear pip install message.
- Terminal build newer than package -> upgrade: pip install -U MetaTrader5.
- Terminal not running/not logged in-> start MT5 and log in, then retry.
- Account invalid/expired demo      -> login error is printed verbatim.

Usage
-----
    python scripts/download_mt5_history.py
    python scripts/download_mt5_history.py --symbols XAUUSD GBPJPY EURUSD --days 730
    python scripts/download_mt5_history.py --terminal-path "C:\\Program Files\\FBS MetaTrader 5\\terminal64.exe"
    python scripts/download_mt5_history.py --server-utc-offset 1

Output
------
    data/raw/{symbol}_{timeframe}.csv
    columns: datetime, open, high, low, close, volume

Timezone handling
-----------------
MetaTrader 5 returns candles stamped in SERVER time. This script converts
them to UTC using ``--server-utc-offset`` (default 3, measured empirically
on the FBS-Demo server: the newest M15 bar's epoch sits exactly 3 hours
ahead of UTC). Both the converted UTC bounds and the raw server bounds are
written into the CSV header so the conversion is auditable. If your broker
uses a different server offset, pass --server-utc-offset (e.g. 1 or 2) and
re-run; do not change the strategy.
"""

import argparse
import glob
import os
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

DEFAULT_TERMINAL_HINTS = [
    os.environ.get("MT5_TERMINAL_PATH", ""),
    r"C:\Program Files\FBS MetaTrader 5\terminal64.exe",
    r"C:\Program Files\MetaTrader 5\terminal64.exe",
    r"C:\Program Files\FBS Markets Inc\terminal64.exe",
]


def find_terminal_path() -> str:
    """Best-effort lookup of an installed terminal64.exe."""
    hints = [h for h in DEFAULT_TERMINAL_HINTS if h]
    for hint in hints:
        if hint and Path(hint).exists():
            return hint
    for base in [r"C:\Program Files", r"C:\Program Files (x86)",
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")]:
        pattern = os.path.join(base, "*MetaTrader*", "terminal64.exe")
        for match in sorted(glob.glob(pattern)):
            return match
    return ""


def init_mt5(mt5, terminal_path: str):
    """Attach to a running/installed MT5 terminal with clear failure text."""
    if terminal_path and not Path(terminal_path).exists():
        print(
            f"ERROR: --terminal-path points at a file that does not exist: "
            f"{terminal_path}",
            file=sys.stderr,
        )
        return False
    if terminal_path:
        if mt5.initialize(path=terminal_path):
            return True
        if mt5.initialize():  # fall back to default discovery
            return True
    else:
        if mt5.initialize():
            return True
        path = find_terminal_path()
        if path and mt5.initialize(path=path):
            return True

    code, text = mt5.last_error()
    print(
        "ERROR: could not connect to the MetaTrader 5 terminal.\n"
        "  1. Make sure the MT5 terminal is OPEN and LOGGED IN to your "
        "broker account.\n"
        "  2. Fix the login inside MT5 (e.g. re-login an expired demo "
        "account), then re-run this script.\n"
        "  3. If your terminal build is newer than the Python package, "
        "upgrade it with:  pip install --upgrade MetaTrader5\n"
        f"  initialize() returned: code={code} text={text!r}",
        file=sys.stderr,
    )
    return False


def export_symbol(
    mt5,
    symbol: str,
    timeframe: str,
    utc_offset_hours: int,
    utc_from: datetime,
    utc_to: datetime,
    output_path: Path,
) -> int:
    """Download one symbol, convert to UTC and write a documented CSV."""
    tf = getattr(mt5, TIMEFRAME_LABELS[timeframe])

    if not mt5.symbol_select(symbol, True):
        print(
            f"ERROR: cannot select symbol '{symbol}': {mt5.last_error()}",
            file=sys.stderr,
        )
        return 1

    rates = mt5.copy_rates_range(symbol, tf, utc_from, utc_to)
    if rates is None or len(rates) == 0:
        print(
            f"ERROR: no {timeframe} history for {symbol} between "
            f"{utc_from:%Y-%m-%d} and {utc_to:%Y-%m-%d}: {mt5.last_error()}",
            file=sys.stderr,
        )
        return 1

    df = pd.DataFrame(rates)
    # MT5 stamps bars in server time; convert to UTC using the offset.
    server_dt = pd.to_datetime(df["time"], unit="s")
    if "tick_volume" in df.columns:
        df["volume"] = df["tick_volume"]
    elif "real_volume" in df.columns:
        df["volume"] = df["real_volume"]
    df["datetime"] = server_dt - pd.Timedelta(hours=utc_offset_hours)
    df = df[["datetime", "open", "high", "low", "close", "volume"]].copy()
    df["datetime"] = df["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df.drop_duplicates(subset="datetime", keep="last", inplace=True)
    df.sort_values("datetime", inplace=True)

    zero_vol = int((df["volume"] <= 0).sum())
    if zero_vol:
        print(
            f"WARNING: {symbol} contains {zero_vol} bars with zero tick volume.",
            file=sys.stderr,
        )

    header = [
        "# source: MetaTrader 5 terminal export "
        "(scripts/download_mt5_history.py) - REAL MARKET DATA",
        f"# symbol: {symbol}",
        f"# timeframe: {timeframe}",
        f"# bars: {len(df)}",
        f"# first_bar_utc: {df['datetime'].iloc[0]}",
        f"# last_bar_utc: {df['datetime'].iloc[-1]}",
        f"# first_bar_server_time: {server_dt.iloc[0]:%Y-%m-%d %H:%M:%S}",
        f"# server_utc_offset_hours: +{utc_offset_hours}",
        "# timezone: UTC (converted from MT5 server time)",
        "# volume: tick volume as reported by the broker",
        "# columns: datetime, open, high, low, close, volume",
    ]
    with output_path.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(header) + "\n")
        df.to_csv(fh, index=False)

    print(
        f"Exported {len(df)} REAL {timeframe} bars for {symbol} "
        f"[{df['datetime'].iloc[0]} .. {df['datetime'].iloc[-1]} UTC] -> {output_path}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download real MT5 M15 history into data/raw as UTC CSV."
    )
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                        help=f"Symbols (default: {' '.join(DEFAULT_SYMBOLS)})")
    parser.add_argument("--timeframe", default="M15",
                        choices=list(TIMEFRAME_LABELS))
    parser.add_argument("--days", type=int, default=730,
                        help="Days of history to request (default: 730)")
    parser.add_argument("--server-utc-offset", type=int, default=3,
                        help="Hours by which MT5 server time leads UTC "
                             "(default 3, measured on FBS-Demo; adjust per "
                             "broker, e.g. 1 or 2)")
    parser.add_argument("--terminal-path", default="",
                        help="Path to terminal64.exe (auto-discovered if empty)")
    parser.add_argument("--output", default=str(Path(__file__).parent.parent / "data" / "raw"),
                        help="Output directory (default: data/raw)")
    args = parser.parse_args()

    try:
        import MetaTrader5 as mt5
    except ImportError as e:
        print(
            "ERROR: MetaTrader5 package is not installed.\n"
            "Install it with:  pip install MetaTrader5\n",
            file=sys.stderr,
        )
        return 1

    if not init_mt5(mt5, args.terminal_path):
        return 1

    try:
        now = datetime.now()
        utc_to = now
        utc_from = now - timedelta(days=args.days)

        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)

        rc = 0
        for symbol in args.symbols:
            rc += export_symbol(
                mt5, symbol, args.timeframe, args.server_utc_offset,
                utc_from, utc_to, output / f"{symbol}_{args.timeframe}.csv",
            )
        return rc
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())