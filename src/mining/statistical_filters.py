"""
Statistical filters for mining results.

Implements the post-processing pipeline that separates genuine edge from luck:

    1. PRIMARY FILTER   - hard trade-count / win / PF / return / drawdown
                          gates, applied to the full period AND each year.
    2. LUCK BASELINE    - identical 1,000-random-entry strategies per asset
                          supply an empirical return distribution; a strategy
                          passes only if its return beats the baseline.
    3. MULTIPLE TESTING - Benjamini-Hochberg FDR correction (q = 0.05) on the
                          empirical p-values, per asset.
    4. COMPOSITE SCORE  - ranking formula:
        PF*20 + WinRate*10 + Sharpe*15 + (Return/MaxDD)*10 + Year2*25
        - ParamSensitivityPenalty*5
"""

import numpy as np

from src.mining.robustness_tests import sensitivity_fraction


# --------------------------------------------------------------------------- #
# Primary filter (Step 7 of the task, exact thresholds).
# --------------------------------------------------------------------------- #
def passes_primary(metrics: dict) -> bool:
    """Hard gates on the full period, plus the same gate relaxed per year."""
    m = metrics
    if not (50 <= m["total_trades"] <= 500):
        return False
    if m["winrate"] < 0.50:
        return False
    if m["profit_factor"] < 1.3:
        return False
    if m["total_return_pct"] < 0.10:
        return False
    if m["max_dd_pct"] > 0.25:
        return False
    if m["expectancy"] <= 0:
        return False

    years = m["years"]
    for yr, y in years.items():
        if y["n"] == 0:
            continue
        if y["winrate"] < 0.45:
            return False
        if y["pf"] < 1.0:
            return False
        if y["return_pct"] < 0.0:
            return False
    return True


# --------------------------------------------------------------------------- #
# Luck baseline / empirical p-values.
# --------------------------------------------------------------------------- #
def p_value_of(return_pct: float, baseline: np.ndarray or list) -> float:
    """Empirical fraction of random-entry strategies with return >= ours."""
    b = np.asarray(baseline, dtype=float)
    if b.size == 0:
        return 1.0
    frac = float(np.mean(b >= return_pct))
    return max(frac, 1.0 / (b.size + 1))   # never a hard zero


def benjamini_hochberg(p_values: list, q: float = 0.05):
    """Return list of (sorted p) that survive FDR at level q (indices in)."""
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    sorted_p = p[order]
    m = len(p)
    if m == 0:
        return []
    thresh = q * np.arange(1, m + 1) / m
    ok = np.where(sorted_p <= thresh)[0]
    if ok.size == 0:
        return []
    k = int(ok.max())                      # largest i with p_(i) <= q*i/m
    return list(order[:k + 1])             # all smaller p's survive too


# --------------------------------------------------------------------------- #
# Composite score (Step 10 of the task, formula applied literally).
# --------------------------------------------------------------------------- #
def composite_score(metrics: dict, year2_return: float,
                    sens_penalty_pct: float) -> float:
    """Ranking used for the top-N selection.

    sens_penalty_pct is the share of sensitivity variants that turned NEGATIVE
    (0.0 perfect robustness -> 1.0 fragile), taken as the -5 penalty scale.
    """
    m = metrics
    base = (
        m["profit_factor"] * 20
        + m["winrate"] * 10
        + m["sharpe"] * 15
        + (m["total_return_pct"] / max(m["max_dd_pct"], 1e-9)) * 10
        + year2_return * 25
    )
    penalty = sens_penalty_pct * 5
    return base - penalty