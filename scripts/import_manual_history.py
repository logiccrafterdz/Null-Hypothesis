"""
Normalize a manually exported MT5 CSV into data/raw/{symbol}_{tf}.csv.

USE WHEN the automated path (scripts/download_mt5_history.py) is impossible,
e.g. MT5 is not installed on the validation machine or the account cannot
log in. You export the CSV yourself from MT5 (Tools > History Center) and
this script converts any reasonable layout into the pipeline's schema:

    datetime, open, high, low, close, volume        (UTC, naive, comment header)

Accepted source layouts (header row auto-detected, case-insensitive):
- MT5 "Export to file" style:  <DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<TICKVOL>,<VOL>,<SPREAD>
- Plain style:                 datetime,open,high,low,close,volume
- Date+time in one column, or timezone-suffixed datetimes.

Timezone handling: MT5 exports are in server local time. The script converts
to UTC using --server-utc-offset (default 1 = FBS GMT+1 North-Africa) and
writes a header comment so the conversion is auditable.

Usage
-----
    python scripts/import_manual_history.py --input path\to\manual.csv --symbol XAUUSD
    python scripts/import_manual_history.py --input manual.csv --symbol GBPJPY --timeframe M15 --server-utc-offset 1
"""

import argparse
import sys
from pathlib import Path

import pandas as pd


OHLC_ALIASES = {
    "open": ["open", "op", "<open>"],
    "high": ["high", "hi", "<high>"],
    "low": ["low", "lo", "<low>"],
    "close": ["close", "cl", "last", "<close>", "<last>"],
    "volume": ["tickvol", "tickvolume", "tick_vol", "vol", "volume", "<tickvol>", "<vol>", "<volume>"],
    "date": ["date", "<date>", "datetime", "time", "<time>"],
}


def _find_col(columns, wanted):
    norm = {c.strip().strip("<").strip(">").lower(): c for c in columns}
    for alias in OHLC_ALIASES[wanted]:
        if alias in norm:
            return norm[alias]
    return None


def normalize(input_path: Path, symbol: str, timeframe: str,
              utc_offset_hours: int, output_path: Path) -> int:
    df = pd.read_csv(
        input_path,
        comment="#",
        parse_dates=False,
        low_memory=False,
    )
    if df.empty:
        print("ERROR: input CSV is empty.", file=sys.stderr)
        return 1

    date_col = _find_col(df.columns, "date")
    if date_col is None:
        print(
            "ERROR: could not find a date/time column in "
            f"{list(df.columns)}.",
            file=sys.stderr,
        )
        return 1

    out = pd.DataFrame(index=df.index)
    try:
        dt = pd.to_datetime(df[date_col])
        if date_col.lower() in ("<time>", "time"):
            # MT5 style has a separate <DATE> column (already matched as
            # date_col when both exist); otherwise assume a full datetime.
            date_only = _find_col(df.columns, "date_major") or _find_col(df.columns, "date")
            if date_only and date_only != date_col and str(df[date_only].dtype) == "object":
                combined = df[date_only].astype(str) + " " + df[date_col].astype(str)
                dt = pd.to_datetime(combined)
        out["datetime"] = dt
    except (ValueError, TypeError) as e:
        print(f"ERROR: could not parse the time column: {e}", file=sys.stderr)
        return 1

    for field in ["open", "high", "low", "close", "volume"]:
        col = _find_col(df.columns, field)
        if col is None:
            print(
                f"ERROR: missing '{field}' column "
                f"(have {list(df.columns)}).",
                file=sys.stderr,
            )
            return 1
        out[field] = pd.to_numeric(df[col], errors="coerce")

    out = out.dropna(subset=["open", "high", "low", "close"])

    # Offset (default 1h for FBS GMT+1) -> UTC, then normalize to a naive
    # UTC column matching the schema expected by load_cached_data().
    aware = out["datetime"].dt.tz_localize("UTC")
    aware = aware - pd.Timedelta(hours=utc_offset_hours)
    aware = aware.astype("datetime64[ns, UTC]")
    out["datetime"] = aware.dt.tz_convert(None).dt.strftime("%Y-%m-%d %H:%M:%S")

    out.drop_duplicates(subset="datetime", keep="last", inplace=True)
    out.sort_values("datetime", inplace=True)
    out["volume"] = out["volume"].fillna(0).astype(int)
    out = out[["datetime", "open", "high", "low", "close", "volume"]]

    header = [
        "# source: manual MT5 History Center export "
        "(scripts/import_manual_history.py) - REAL MARKET DATA",
        f"# symbol: {symbol}",
        f"# timeframe: {timeframe}",
        f"# bars: {len(out)}",
        f"# first_bar_utc: {out['datetime'].iloc[0]}",
        f"# last_bar_utc: {out['datetime'].iloc[-1]}",
        f"# server_utc_offset_hours: +{utc_offset_hours}",
        "# timezone: UTC (converted from MT5 server time)",
        f"# source_file: {input_path}",
        "# columns: datetime, open, high, low, close, volume",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(header) + "\n")
        out.to_csv(fh, index=False)

    print(
        f"Imported {len(out)} rows ({symbol} {timeframe}) "
        f"[{out['datetime'].iloc[0]} .. {out['datetime'].iloc[-1]} UTC] -> {output_path}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize a manual MT5 CSV export.")
    parser.add_argument("--input", required=True, help="Path to the exported CSV")
    parser.add_argument("--symbol", required=True, help="Symbol (e.g. XAUUSD)")
    parser.add_argument("--timeframe", default="M15")
    parser.add_argument("--server-utc-offset", type=int, default=1,
                        help="Hours by which MT5 server time leads UTC (default 1)")
    parser.add_argument("--output", default="",
                        help="Output data/raw directory (default: project data/raw)")
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else (
        Path(__file__).parent.parent / "data" / "raw"
    )
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 1

    return normalize(
        input_path, args.symbol, args.timeframe,
        args.server_utc_offset, output_dir / f"{args.symbol}_{args.timeframe}.csv",
    )


if __name__ == "__main__":
    sys.exit(main())