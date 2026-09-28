"""
Statistical Test Runner (spec section 6C).

Rule enforced here: nothing downstream is allowed to assert significance
or an effect size that wasn't actually computed by one of these functions.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats

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
    slope, _, r_value, p_value, _ = stats.linregress(x, y)
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
