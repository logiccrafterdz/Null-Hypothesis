"""
Generate deterministic synthetic M15 OHLCV fixtures for pipeline validation.

Phase 2 Option B of the post-fix validation bootstrap: generates realistic
synthetic data (trending up, trending down, ranging, high volatility and
capitulation events) so the corrected pipeline can be validated without any
MT5 terminal or live credentials.

IMPORTANT
---------
Synthetic data is for PIPELINE VALIDATION ONLY. It must never be used to
claim real strategy performance. Use scripts/download_mt5_history.py to pull
real history when a terminal is available.

Usage
-----
    python scripts/generate_synthetic_data.py --symbol XAUUSD GBPJPY EURUSD --days 365
    python scripts/generate_synthetic_data.py --symbol XAUUSD --days 365 --seed 42 --regime high_vol
    python scripts/generate_synthetic_data.py --symbol XAUUSD --output data/raw/synthetic_M15.csv

Default output is data/raw/{symbol}_{timeframe}.csv so the local pipeline
(DATA_SOURCE=local) can consume the fixtures directly.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.helpers import generate_sample_data  # noqa: E402

DEFAULT_SYMBOLS = ["XAUUSD", "GBPJPY", "EURUSD"]
REGIMES = ["mixed", "trend_up", "trend_down", "ranging", "high_vol"]


def _seeded(seed: int, symbol: str, timeframe: str, days: int, regime: str) -> int:
    """Stable per-configuration seed so runs are reproducible."""
    raw = hash((seed, symbol, timeframe, days, regime))
    return (raw % (2 ** 31 - 1))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate synthetic OHLCV fixtures for pipeline validation."
    )
    parser.add_argument("--symbol", nargs="+", default=DEFAULT_SYMBOLS,
                        help="Symbol(s) (default: XAUUSD GBPJPY EURUSD)")
    parser.add_argument("--days", type=int, default=365,
                        help="Days of synthetic history (default: 365)")
    parser.add_argument("--timeframe", default="M15",
                        help="Bar timeframe (default: M15)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Base random seed (default: 42)")
    parser.add_argument("--regime", default="mixed", choices=REGIMES,
                        help="Market regime to synthesize (default: mixed)")
    parser.add_argument("--output",
                        default=str(Path(__file__).parent.parent / "data" / "raw"),
                        help="Output file or directory (default: data/raw)")
    args = parser.parse_args()

    output = Path(args.output)
    if output.suffix.lower() == ".csv":
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
        seed = _seeded(args.seed, symbol, args.timeframe, args.days, args.regime)
        df = generate_sample_data(
            asset=symbol,
            days=args.days,
            timeframe=args.timeframe,
            seed=seed,
            regime=args.regime,
        )

        header = [
            "# source: synthetic (scripts/generate_synthetic_data.py)",
            f"# symbol: {symbol}",
            f"# timeframe: {args.timeframe}",
            f"# regime: {args.regime}",
            f"# seed: {seed}",
            "# WARNING: synthetic data - PIPELINE VALIDATION ONLY",
            "# columns: datetime, open, high, low, close, volume",
        ]
        with csv_path.open("w", encoding="utf-8") as fh:
            fh.write("\n".join(header) + "\n")
            df.reset_index().rename(columns={"index": "datetime"}).to_csv(
                fh, index=False
            )
        print(f"Generated {len(df)} synthetic bars for {symbol} {args.timeframe} -> {csv_path}")
        rc += 0

    return rc


if __name__ == "__main__":
    sys.exit(main())