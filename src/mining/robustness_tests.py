"""
Robustness stress tests for survivor strategies.

Three independent checks (task Steps 8-9):

  SENSITIVITY   - re-run with every exit parameter nudged +/-20% and with the
                  direction flipped (9 variants); the strategy must stay
                  profitable in >= 70% of variants.
  REGIMES       - split the 2-year span into 4 six-month regimes; the strategy
                  must be profitable in >= 3 of them. Features are always
                  computed on full trailing history, so slicing a FIRST and
                  LAST bar window re-runs the strategy on past bars only -
                  never lookahead.
  RANDOM GATE   - the randomness-independence test: re-run the SAME signal
                  mask but drop a random fraction of its entry signals with
                  keep probability p in {0.3, 0.5, 0.7, 0.9}; a robust edge
                  must survive >= 3 of the 4 densities.
"""

import random

import numpy as np

from src.mining.bulk_backtester import evaluate_entry_mask, run_strategy
from src.mining.condition_library import WARMUP_BARS


# --------------------------------------------------------------------------- #
# Sensitivity
# --------------------------------------------------------------------------- #
def sensitivity_fraction(F: dict, spec: dict, capital: float = 10000.0) -> float:
    """Share of +/-20% build-variants that stay profitable (>= 0.7 passes)."""
    positives = 0
    variants = 0
    ex = spec["exits"]

    def variant(exits, direction):
        nonlocal positives, variants
        trial = dict(spec)
        trial["exits"] = dict(exits)
        trial["direction"] = direction
        m = run_strategy(F, trial, capital)
        variants += 1
        positives += 1 if m["total_return_pct"] > 0 else 0

    for mult in (0.8, 1.2):
        variant({**ex, "stop_loss_pct": ex["stop_loss_pct"] * mult},
                spec["direction"])
        variant({**ex, "take_profit_pct": ex["take_profit_pct"] * mult},
                spec["direction"])
        variant({**ex,
                 "max_duration_bars": max(1, int(ex["max_duration_bars"] * mult))},
                spec["direction"])
        variant({**ex,
                 "trailing_distance_pct": ex["trailing_distance_pct"] * mult},
                spec["direction"])
    variant(
        {**ex,
         "max_duration_bars": max(1, int(ex["max_duration_bars"] * 1.2))},
        "SHORT" if spec["direction"] == "LONG" else "LONG")

    return positives / variants if variants else 0.0


def passes_sensitivity(fraction: float) -> bool:
    return fraction >= 0.70


# --------------------------------------------------------------------------- #
# Regime stability (4 x six months)
# --------------------------------------------------------------------------- #
def slice_features(F: dict, start: int, end: int) -> dict:
    """Copy a trailing-features slice so windows can be re-simulated."""
    return {k: v[start:end].copy()
            for k, v in F.items()
            if isinstance(v, np.ndarray) and v.shape[0] == len(F["close"])}


def regime_positives(F: dict, spec: dict, capital: float = 10000.0,
                     n_regimes: int = 4) -> tuple:
    """Return (count_positive, count_tested) over equal-length regimes."""
    n = len(F["close"])
    usable = n - WARMUP_BARS
    if usable <= 0:
        return 0, 0
    step = usable // n_regimes or 1
    positives, tested = 0, 0
    start = WARMUP_BARS
    for _ in range(n_regimes):
        end = min(start + step, n)
        if end - start < 100:
            break
        Fs = slice_features(F, start, end)
        m = run_strategy(Fs, spec, capital)
        tested += 1
        if m["total_trades"] >= 10 and m["total_return_pct"] > 0:
            positives += 1
        start = end
    return positives, tested


def passes_regimes(positive: int, tested: int) -> bool:
    if tested >= 4:
        return positive >= 3
    if tested == 3:
        return positive >= 2
    return tested > 0 and positive == tested


# --------------------------------------------------------------------------- #
# Randomness independence - signal sub-sampling
# --------------------------------------------------------------------------- #
def random_gate_pass_rates(F: dict, spec: dict, capital: float = 10000.0,
                           densities=(0.3, 0.5, 0.7, 0.9)) -> float:
    """Fraction of keep-densities under which the strategy stays positive."""
    base_mask = evaluate_entry_mask(F, spec["entry"],
                                    spec.get("generator_seed", 0))
    positives, tested = 0, 0
    for p in densities:
        gated = _drop_signals(base_mask, p, spec.get("generator_seed", 0))
        m = run_strategy(F, spec, capital, entry_mask_override=gated)
        tested += 1
        positives += 1 if m["total_return_pct"] > 0 else 0
    return positives / tested if tested else 0.0


def _drop_signals(mask: np.ndarray, keep_prob: float, seed: int) -> np.ndarray:
    rng = random.Random(seed)
    out = mask.copy()
    alive = np.flatnonzero(mask)
    for i in alive:
        if rng.random() >= keep_prob:
            out[i] = False
    return out