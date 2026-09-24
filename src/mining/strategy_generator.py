"""
Random strategy generator.

Creates reproducible random strategies over the condition library. Each
strategy spec is a plain dict (YAML/JSON friendly) containing:

    - unique id
    - asset / timeframe
    - direction (LONG / SHORT)
    - entry: {operator, conditions: [{type, params}, ...]}
    - exits: randomized stop / take profit / trailing / max duration
    - risk: 2% per trade, max 2 open positions (fixed, mirrors production)
    - seed that produced it (for exact reproduction)

Generator contract: given (seed, asset, timeframe) the same spec is always
produced. Condition parameters are drawn from CONDITION_TEMPLATES valid
spaces, so nothing asset-tuned enters the spec.
"""

import random
from datetime import datetime, timezone

from src.mining.condition_library import CONDITION_TEMPLATES


class StrategyGenerator:
    """Random reproducible strategy factory."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.rng = random.Random(seed)

    def _pick(self, choices):
        return self.rng.choice(list(choices))

    def _rand_conditions(self) -> list:
        n_conditions = self.rng.randint(2, 5)
        types = self.rng.sample(sorted(CONDITION_TEMPLATES.keys()), n_conditions)
        conds = []
        for t in types:
            params = {}
            for pname, choices in CONDITION_TEMPLATES[t]["params"].items():
                params[pname] = self._pick(choices)
            conds.append({"type": t, "params": params})
        return conds

    def _rand_exits(self) -> dict:
        stop = self.rng.choice([0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02,
                                0.025, 0.03])
        tp = self.rng.choice([0.005, 0.0075, 0.01, 0.015, 0.02, 0.03,
                              0.04, 0.05])
        trailing = self.rng.random() < 0.5
        return {
            "stop_loss_pct": stop,
            "take_profit_pct": tp,
            "trailing": trailing,
            "trailing_activation_pct": self.rng.choice([0.005, 0.01, 0.015, 0.02]),
            "trailing_distance_pct": self.rng.choice([0.003, 0.005, 0.008, 0.01, 0.015]),
            "max_duration_bars": self.rng.randint(5, 50),
        }

    def generate(self, asset: str, timeframe: str = "M15",
                 direction: str = None) -> dict:
        """Produce one strategy spec from the current RNG state."""
        if direction is None:
            direction = "LONG" if self.rng.random() < 0.5 else "SHORT"
        operator = self.rng.choice(["and", "or", "mixed"])
        spec = {
            "id": f"{asset}_{timeframe}_{self.rng.getrandbits(16):05d}",
            "asset": asset,
            "timeframe": timeframe,
            "direction": direction,
            "entry": {
                "operator": operator,
                "conditions": self._rand_conditions(),
            },
            "exits": self._rand_exits(),
            "risk": {"risk_per_trade": 0.02, "max_open": 2},
            "generator_seed": self.rng.getrandbits(31),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        return spec

    def generate_sequence(self, asset: str, count: int,
                          timeframe: str = "M15") -> list:
        """Generate *count* distinct strategies for one asset."""
        out = []
        seen = set()
        guard = 0
        while len(out) < count and guard < count * 50:
            spec = self.generate(asset, timeframe)
            if spec["id"] in seen:
                guard += 1
                continue
            seen.add(spec["id"])
            out.append(spec)
        return out

    def generate_random_entry(self, asset: str, timeframe: str = "M15",
                              density: float = 0.01,
                              direction: str = None) -> dict:
        """A pure-luck control: random entry mask, randomised exits."""
        if direction is None:
            direction = "LONG" if self.rng.random() < 0.5 else "SHORT"
        return {
            "id": f"LUCK_{asset}_{timeframe}_{self.rng.getrandbits(16):05d}",
            "asset": asset,
            "timeframe": timeframe,
            "direction": direction,
            "entry": {
                "operator": "random",
                "conditions": [],
                "density": density,
            },
            "exits": self._rand_exits(),
            "risk": {"risk_per_trade": 0.02, "max_open": 2},
            "generator_seed": self.rng.getrandbits(31),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }


def generated_range(asset: str, count: int, base_seed: int = 2026,
                    timeframe: str = "M15") -> list:
    """Generate a deterministic block of strategies for an asset."""
    gen = StrategyGenerator(seed=base_seed)
    return gen.generate_sequence(asset, count, timeframe)