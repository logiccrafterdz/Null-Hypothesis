"""
Chaos Discovery Engine - mining session orchestrator.

Runs the full random-hypothesis-mining pipeline on real FBS data:

    features -> random strategy pool -> bulk backtest -> luck baseline
    -> primary filter -> robustness tests -> FDR multiple-testing
    -> composite score -> top-N -> reports + mined strategy YAML

Run:
    python scripts/run_mining_session.py                  # full pass
    python scripts/run_mining_session.py --quota 1000     # fast scale-down
    python scripts/run_mining_session.py --validate-only  # backtester check

Never touches production code: backtest, risk and trade rules are mirrored
locally in src/mining and the output is research only.
"""

import argparse
import json
import multiprocessing
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mining.bulk_backtester import run_strategy  # noqa: E402
from src.mining.condition_library import build_features, load_real_data  # noqa: E402
from src.mining.robustness_tests import (  # noqa: E402
    passes_regimes,
    passes_sensitivity,
    random_gate_pass_rates,
    regime_positives,
    sensitivity_fraction,
)
from src.mining.statistical_filters import (  # noqa: E402
    benjamini_hochberg,
    composite_score,
    p_value_of,
    passes_primary,
)
from src.mining.strategy_generator import StrategyGenerator  # noqa: E402

REPORTS = ROOT / "reports"
MINED = ROOT / "config" / "mined_strategies"
CAPITAL = 10000.0

PRODUCTION_EXITS = {
    "stop_loss_pct": 0.015,
    "take_profit_pct": 0.03,
    "trailing": True,
    "trailing_activation_pct": 0.015,
    "trailing_distance_pct": 0.005,
    "max_duration_bars": 15,
}


def reference_spec(asset: str = "XAUUSD"):
    """The Phase-8 research candidate used to validate this backtester."""
    return {
        "id": "VALIDATION_XAUUSD_M15",
        "asset": asset,
        "timeframe": "M15",
        "direction": "LONG",
        "entry": {
            "operator": "and",
            "conditions": [
                {"type": "drop_gt", "params": {"x": 0.2}},
                {"type": "vol_ratio_prev", "params": {"x": 1.5}},
            ],
        },
        "exits": dict(PRODUCTION_EXITS),
        "risk": {"risk_per_trade": 0.02, "max_open": 2},
        "generator_seed": 0,
    }


def _research_seed(cfg) -> int:
    """Seed used for `cfg` in the Phase-8 research run (SEED_BASE + row index)."""
    from scripts.analyze_signal_feasibility import (  # noqa: F811
        load_data, prepare_features, shortlist_configs)
    from scripts.run_research_backtests import SEED_BASE  # noqa: F811
    data = {k: prepare_features(df, k[1]) for k, df in load_data().items()}
    for n, c in enumerate(shortlist_configs(data)):
        if (c["sym"], c["tf"], c["drop"], c.get("rule"),
                c.get("kind")) == (cfg["sym"], cfg["tf"], cfg["drop"],
                                   cfg["rule"], cfg["kind"]):
            return SEED_BASE + n
    return SEED_BASE


def validate_backtester(F, asset: str) -> dict:
    """Two independent checks.

    1. GROUND TRUTH: reproduce the recorded Phase-8 research result using the
       exact reference simulation. XAUUSD M15 drop=0.002 ratio=1.5 has a
       recorded outcome (336 executed, -35.69%).
    2. ENGINE EQUIVALENCE: run the same candidate in THIS backtester (no
       randomness gate) and in the reference simulation with the gate
       disabled; both must agree on trades and return.
    """
    from scripts.analyze_signal_feasibility import prepare_features
    from scripts.run_research_backtests import CandidateSim, SEED_BASE

    df = _features_index_frame(F)
    feats = prepare_features(df, "M15")
    cfg = {"sym": asset, "tf": "M15", "drop": 0.002, "rule": 1.5,
           "kind": "ratio"}

    seed = _research_seed(cfg)
    ref = CandidateSim(feats, cfg, CAPITAL).run(seed, 0.6)
    no_gate = CandidateSim(feats, cfg, CAPITAL).run(seed, 1.0)
    engine = run_strategy(F, reference_spec(asset), CAPITAL)

    recorded = None
    if asset == "XAUUSD":
        recorded = {"signals": 983, "executed": 336, "return_pct": -0.3569}
        gt_ok = (ref["signals"] == recorded["signals"]
                 and abs(ref["executed"] - recorded["executed"]) <= 2
                 and abs(ref["ret_pct"] - recorded["return_pct"]) <= 0.005)
    else:
        gt_ok = ref["signals"] == no_gate["signals"]  # mask check only

    eq = (abs(engine["total_trades"] - no_gate["executed"]) <= 20
          and abs(engine["total_return_pct"] - no_gate["ret_pct"]) <= 0.03
          and abs(engine["counters"]["signals"] - no_gate["signals"]) <= 5)
    return {
        "ground_truth": {
            "signals": ref["signals"], "executed": ref["executed"],
            "return_pct": round(ref["ret_pct"], 4),
        },
        "recorded": recorded,
        "ground_truth_matches_report": gt_ok,
        "reference_no_gate": {"trades": no_gate["executed"],
                              "return_pct": round(no_gate["ret_pct"], 4)},
        "engine": {"trades": engine["total_trades"],
                   "return_pct": round(engine["total_return_pct"], 4),
                   "signals": int(engine["counters"]["signals"])},
        "engine_equivalent": eq,
        "ok": gt_ok and eq,
    }


def _features_index_frame(F: dict):
    import pandas as pd
    return pd.DataFrame(
        {k: F[k] for k in ("open", "high", "low", "close", "volume")},
        index=F["_index"],)


_WORKER_F = None
_MAX_WORKERS = max(1, min(8, (os.cpu_count() or 4)))


def _init_worker(F):
    global _WORKER_F
    _WORKER_F = F


def _run_one(spec):
    """Worker entry: backtest a single spec against the shared features."""
    res = run_strategy(_WORKER_F, spec, CAPITAL)
    res["spec"] = spec
    return res


def run_pool(F, specs, label, progress_every=250, parallel=True):
    t0 = time.time()
    results = []
    if not parallel or len(specs) < progress_every:
        for i, spec in enumerate(specs):
            results.append(_run_one(spec))
            if (i + 1) % progress_every == 0:
                el = time.time() - t0
                print(f"  [{label}] {i+1}/{len(specs)} done "
                      f"({el:.1f}s, {el/(i+1)*1000:.0f} ms/strategy)")
        return results
    with ProcessPoolExecutor(max_workers=_MAX_WORKERS,
                             initializer=_init_worker, initargs=(F,)) as ex:
        for chunk_start in range(0, len(specs), progress_every):
            chunk = specs[chunk_start:chunk_start + progress_every]
            chunk_size = max(1, len(chunk) // _MAX_WORKERS)
            chunk_res = list(ex.map(_run_one, chunk, chunksize=chunk_size))
            results.extend(chunk_res)
            el = time.time() - t0
            print(f"  [{label}] {len(results)}/{len(specs)} done "
                  f"({el:.1f}s, {el/max(1,len(results))*1000:.0f} ms/strategy)")
    return results


PARTIAL = REPORTS / "_mining_session_partial.json"


def _dump_partial(session):
    """Persist everything the reports need so a crash never wastes compute."""
    slim = {
        "generated_at": session["generated_at"],
        "assets": session["assets"],
        "quota_per_asset": session["quota_per_asset"],
        "luck_baseline_per_asset": session["luck_baseline_per_asset"],
        "seed": session["seed"],
        "capital": session["capital"],
        "validation": session["validation"],
        "assets_results": {
            asset: {
                "n_generated": ar["n_generated"],
                "n_primary": ar["n_primary"],
                "n_robust": ar["n_robust"],
                "n_final": ar["n_final"],
                "top": ar["top"],
                "luck": ar.get("luck", {}),
                "final": [_clean(m) for m in ar["final"]],
            } for asset, ar in session["assets_results"].items()
        },
    }
    PARTIAL.write_text(json.dumps(_clean(slim), indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Run a mining session")
    ap.add_argument("--assets", nargs="+", default=["XAUUSD", "EURUSD"])
    ap.add_argument("--quota", type=int, default=5000,
                    help="random strategies per asset (task: 5000 each)")
    ap.add_argument("--luck", type=int, default=1000,
                    help="random-entry baseline strategies per asset")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--finalize-only", action="store_true",
                    help="rebuild reports from the saved partial session")
    args = ap.parse_args()

    REPORTS.mkdir(exist_ok=True)
    MINED.mkdir(exist_ok=True)

    if args.finalize_only:
        if not PARTIAL.exists():
            print(f"no partial session found: {PARTIAL}")
            sys.exit(1)
        data = json.loads(PARTIAL.read_text(encoding="utf-8"))
        session = {
            "generated_at": data["generated_at"],
            "assets": data["assets"],
            "quota_per_asset": data["quota_per_asset"],
            "luck_baseline_per_asset": data["luck_baseline_per_asset"],
            "seed": data["seed"],
            "capital": data["capital"],
            "validation": data["validation"],
            "assets_results": data["assets_results"],
        }
        build_reports(session)
        summary = _clean(session_summary(session))
        print("=== FINALIZED SESSION SUMMARY ===")
        print(json.dumps(summary, indent=2))
        (REPORTS / "mining_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8")
        return 0

    session = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "assets": list(args.assets),
        "quota_per_asset": args.quota,
        "luck_baseline_per_asset": args.luck,
        "seed": args.seed,
        "capital": CAPITAL,
        "validation": {},
        "assets_results": {},
    }

    for asset in args.assets:
        print(f"\n=== Asset: {asset} ===")
        df = load_real_data(asset, "M15")
        F = build_features(df)
        print(f"  bars: {len(df)}  span: {df.index[0]} -> {df.index[-1]}")

        val = validate_backtester(F, asset)
        print(f"  validation ok={val['ok']} "
              f"ground={val['ground_truth']} "
              f"engine={val['engine']} equivalence="
              f"{val['engine_equivalent']}")
        session["validation"][asset] = val
        if args.validate_only:
            continue
        if not val["ok"]:
            print("  ABORT: backtester validation failed for this asset.")
            sys.exit(1)

        gen = StrategyGenerator(seed=args.seed + (0 if asset == "XAUUSD" else 137))
        specs = gen.generate_sequence(asset, args.quota)

        print(f"  backtesting {len(specs)} strategies ...")
        results = run_pool(F, specs, asset)

        print(f"  generating {args.luck} luck-baseline strategies ...")
        luck_specs = [gen.generate_random_entry(asset, "M15", density=0.01)
                      for _ in range(args.luck)]
        luck = run_pool(F, luck_specs, f"luck/{asset}")

        asset_res = process_asset(F, asset, results, luck, gen)
        session["assets_results"][asset] = asset_res
        dump_asset_results(asset_res, asset)
        _dump_partial(session)

    if not args.validate_only:
        build_reports(session)
        summary = _clean(session_summary(session))
        print("\n=== SESSION SUMMARY ===")
        print(json.dumps(summary, indent=2))
        (REPORTS / "mining_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8")


def process_asset(F, asset, results, luck, gen):
    luck_returns = [r["total_return_pct"] for r in luck]

    survivors = [m for m in results if passes_primary(m)]
    print(f"  primary filter survivors: {len(survivors)}/{len(results)}")

    for m in survivors:
        m["luck_p"] = p_value_of(m["total_return_pct"], luck_returns)
        m["luck_p95"] = m["total_return_pct"] > _pct95(luck_returns)

    robust = []
    for m in survivors:
        sens = sensitivity_fraction(F, _spec_of(m), CAPITAL)
        rp, rt = regime_positives(F, _spec_of(m), CAPITAL)
        gate = random_gate_pass_rates(F, _spec_of(m), CAPITAL)
        m["sens"] = sens
        m["regimes"] = (rp, rt)
        m["gate"] = gate
        if passes_sensitivity(sens) and passes_regimes(rp, rt) and gate >= 0.75:
            robust.append(m)
    print(f"  robustness survivors: {len(robust)}/{len(survivors)}")

    p_vals = [m["luck_p"] for m in robust]
    keep_idx = set(benjamini_hochberg(p_vals, q=0.05))
    fdr_survivors = []
    for j, m in enumerate(robust):
        if j in keep_idx or m["luck_p95"]:
            fdr_survivors.append(m)
    print(f"  FDR + p95 survivors: {len(fdr_survivors)}/{len(robust)}")

    for m in fdr_survivors:
        yr = [y for y in m["years"].values()][-1] if m["years"] else None
        m["year2_return"] = yr["return_pct"] if yr else 0.0
        m["total_pnl"] = m["expectancy"] * m["total_trades"]
        m["composite"] = composite_score(
            m, m["year2_return"],
            1.0 - m["sens"])                     # penalty = fragile share
        m["spec"] = _spec_of(m)

    fdr_survivors.sort(key=lambda m: m["composite"], reverse=True)
    top = fdr_survivors[:5]

    print(f"  TOP {len(top)} selected for {asset}")
    for m in top:
        print(f"    {m['id']} score={m['composite']:.1f} "
              f"ret={m['total_return_pct']*100:.1f}% "
              f"trades={m['total_trades']} pf={m['profit_factor']:.2f}")

    dump_mined_strategies(top, asset)
    import numpy as np
    luck_mean = float(np.mean(luck_returns))
    luck_p95 = float(np.percentile(np.asarray(luck_returns), 95))
    return {
        "n_generated": len(results),
        "n_primary": len(survivors),
        "n_robust": len(robust),
        "n_final": len(fdr_survivors),
        "top": [t["id"] for t in top],
        "luck_returns": luck_returns,
        "luck": {"n": len(luck_returns), "mean": luck_mean, "p95": luck_p95},
        "final": fdr_survivors,
    }


def _spec_of(m):
    return m["spec"]


def _clean(obj):
    """Recursively convert numpy scalars to plain Python for yaml/json."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def _pct95(x):
    return float(np.percentile(np.asarray(x, dtype=float), 95))


def dump_asset_results(asset_res, asset):
    final = asset_res["final"]
    blob = {
        "asset": asset,
        "primary": asset_res["n_primary"],
        "robust": asset_res["n_robust"],
        "final": asset_res["n_final"],
        "metrics": [compact(m) for m in final],
    }
    (REPORTS / f"mining_{asset}_results.json").write_text(
        json.dumps(_clean(blob), indent=2), encoding="utf-8")


def compact(m):
    return {k: m[k] for k in (
        "id", "direction", "total_trades", "winrate", "profit_factor",
        "total_return_pct", "max_dd_pct", "sharpe", "expectancy", "luck_p",
        "luck_p95", "sens", "composite")}


def dump_mined_strategies(top, asset):
    for m in top:
        payload = {
            "id": m["spec"]["id"],
            "asset": asset,
            "timeframe": "M15",
            "discovered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "direction": m["spec"]["direction"],
            "entry": m["spec"]["entry"],
            "exits": m["spec"]["exits"],
            "risk": m["spec"]["risk"],
            "metrics": compact(m),
            "status": "research_candidate",
        }
        path = MINED / f"{asset}_top_{m['spec']['id']}.yaml"
        path.write_text(yaml.safe_dump(_clean(payload), sort_keys=False),
                        encoding="utf-8")
        print(f"  wrote {path.name}")


def build_reports(session):
    _write_mining_summary(session)
    _write_top_strategies(session)


def _write_mining_summary(session):
    lines = [
        "# Mining Session Summary - Chaos Discovery Engine",
        "",
        f"- Generated: {session['generated_at']}",
        f"- Assets: {', '.join(session['assets'])}",
        f"- Quota per asset: {session['quota_per_asset']}",
        f"- Luck baseline per asset: {session['luck_baseline_per_asset']}",
        f"- Seed: {session['seed']}",
        "",
        "## Backtester validation (reference reproduction)",
        "",
        "| Asset | Signals | Executed (0.6 gate) | Return (ref) | Engine "
        "trades | Engine ret | Matches report | Engine == ref sim |",
        "|---|---:|---:|---:|---:|---:|:---:|:---:|",
    ]
    for asset, val in session["validation"].items():
        gt = val["ground_truth"]
        en = val["engine"]
        lines.append(
            f"| {asset} | {gt['signals']} | {gt['executed']} | "
            f"{gt['return_pct']*100:.2f}% | {en['trades']} | "
            f"{en['return_pct']*100:.2f}% | "
            f"{'yes' if val['ground_truth_matches_report'] else 'NO'} | "
            f"{'yes' if val['engine_equivalent'] else 'NO'} |")
    lines.append("")
    lines.append("## Per-asset funnel")
    lines.append("")
    lines.append("| Asset | Generated | Luck baseline (mean / p95) | "
                 "Primary filter | Robustness | FDR + p95 | Top N |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for asset, ar in session["assets_results"].items():
        lk = ar.get("luck", {})
        lines.append(
            f"| {asset} | {ar['n_generated']} | "
            f"{lk.get('n', 0)} ({lk.get('mean', 0)*100:.1f}% / "
            f"{lk.get('p95', 0)*100:.1f}%) | {ar['n_primary']} | "
            f"{ar['n_robust']} | {ar['n_final']} | {len(ar['top'])} |")

    with open(ROOT / "reports" / "mining_summary.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _write_top_strategies(session):
    lines = ["# Top Mined Strategies Report", ""]
    for asset, ar in session["assets_results"].items():
        lines.append(f"## {asset}")
        lines.append("")
        if not ar["final"]:
            lines.append("_No strategy survived the statistical filters. "
                         "Outcome: NO-GO._")
            lines.append("")
            continue
        lines.append("| Rank | id | Direction | Trades | Win% | PF | Return% "
                     "| MaxDD% | Sharpe | p(luck) | Sens% | Composite |")
        lines.append("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for rank, m in enumerate(ar["final"][:5], start=1):
            lines.append(
                f"| {rank} | {m['id']} | {m['direction']} | {m['total_trades']} | "
                f"{m['winrate']*100:.1f} | {m['profit_factor']:.2f} | "
                f"{m['total_return_pct']*100:.1f} | {m['max_dd_pct']*100:.1f} | "
                f"{m['sharpe']:.2f} | {m['luck_p']:.4f} | "
                f"{m['sens']*100:.0f} | {m['composite']:.1f} |")
        lines.append("")
    lines.append("> Methodology and caveats: see mining_summary.md and "
                 "AGENTS.md / README.")
    with open(ROOT / "reports" / "top_strategies_report.md", "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def session_summary(session):
    sum_ = {
        "generated_at": session["generated_at"],
        "validation": session["validation"],
        "assets": {},
    }
    for asset, ar in session["assets_results"].items():
        sum_["assets"][asset] = {
            "generated": ar["n_generated"],
            "primary_survivors": ar["n_primary"],
            "robust_survivors": ar["n_robust"],
            "final_survivors": ar["n_final"],
            "top5": ar["top"],
        }
    return sum_


if __name__ == "__main__":
    if multiprocessing.parent_process() is None:
        sys.exit(main())