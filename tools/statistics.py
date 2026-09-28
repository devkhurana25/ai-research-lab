"""
Statistical Test Runner (spec section 6C).

Rule enforced here: nothing downstream is allowed to assert significance
or an effect size that wasn't actually computed by one of these functions.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats


def compare_groups(df: pd.DataFrame, value_col: str, group_col: str) -> dict:
    """Two-sample comparison. Picks Welch's t-test; flags assumption checks."""
    groups = df[[value_col, group_col]].dropna()
    labels = groups[group_col].unique()
    if len(labels) != 2:
        return {"error": f"{group_col} must have exactly 2 groups, found {len(labels)}"}

    a = groups[groups[group_col] == labels[0]][value_col]
    b = groups[groups[group_col] == labels[1]][value_col]

    if len(a) < 3 or len(b) < 3:
        return {"error": "insufficient sample size for a reliable test", "n_a": len(a), "n_b": len(b)}

    _, p_norm_a = stats.shapiro(a) if len(a) <= 5000 else (None, None)
    _, p_norm_b = stats.shapiro(b) if len(b) <= 5000 else (None, None)
    normal_ok = (p_norm_a is not None and p_norm_a > 0.05) and (p_norm_b is not None and p_norm_b > 0.05)

    t_stat, p_value = stats.ttest_ind(a, b, equal_var=False)
    pooled_std = np.sqrt((a.std(ddof=1) ** 2 + b.std(ddof=1) ** 2) / 2)
    cohens_d = (a.mean() - b.mean()) / pooled_std if pooled_std > 0 else 0.0

    return {
        "test": "Welch's t-test",
        "group_a": {"label": str(labels[0]), "n": len(a), "mean": float(a.mean())},
        "group_b": {"label": str(labels[1]), "n": len(b), "mean": float(b.mean())},
        "t_statistic": float(t_stat),
        "p_value": float(p_value),
        "significant_at_0.05": bool(p_value < 0.05),
        "effect_size_cohens_d": float(cohens_d),
        "normality_assumption_met": normal_ok,
        "assumption_warning": None if normal_ok else "Normality assumption questionable (Shapiro-Wilk); interpret p-value with caution.",
    }


def correlation_test(df: pd.DataFrame, col_a: str, col_b: str) -> dict:
    pair = df[[col_a, col_b]].dropna()
    if len(pair) < 4:
        return {"error": "insufficient data points for correlation test", "n": len(pair)}
    r, p_value = stats.pearsonr(pair[col_a], pair[col_b])
    return {
        "test": "Pearson correlation",
        "n": len(pair),
        "r": float(r),
        "p_value": float(p_value),
        "significant_at_0.05": bool(p_value < 0.05),
        "strength": (
            "negligible" if abs(r) < 0.1 else
            "weak" if abs(r) < 0.3 else
            "moderate" if abs(r) < 0.5 else
            "strong"
        ),
    }


def trend_over_time(df: pd.DataFrame, time_col: str, value_col: str) -> dict:
    """Simple linear regression of value against time index — for 'did X decline' questions."""
    d = df[[time_col, value_col]].dropna().copy()
    if len(d) < 4:
        return {"error": "insufficient points for trend analysis", "n": len(d)}
    d = d.sort_values(time_col)
    x = np.arange(len(d))
    y = d[value_col].values
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    pct_change = ((y[-1] - y[0]) / y[0] * 100) if y[0] != 0 else None
    return {
        "test": "linear trend (OLS)",
        "n": len(d),
        "slope_per_period": float(slope),
        "r_squared": float(r_value ** 2),
        "p_value": float(p_value),
        "direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "flat",
        "significant_at_0.05": bool(p_value < 0.05),
        "total_pct_change_first_to_last": None if pct_change is None else round(float(pct_change), 2),
    }
