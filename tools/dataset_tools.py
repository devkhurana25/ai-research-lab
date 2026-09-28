"""
Dataset Inspector (spec section 7 / 21).

Pure deterministic profiling. The LLM/agent layer reads this output;
it never invents these numbers itself.
"""
from __future__ import annotations
import pandas as pd
import numpy as np


def load(path: str) -> pd.DataFrame:
    if path.endswith(".csv"):
        return pd.read_csv(path)
    if path.endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    raise ValueError(f"Unsupported dataset type: {path}")


def profile(path: str) -> dict:
    df = load(path)
    n_rows, n_cols = df.shape

    missing = df.isna().sum()
    missing_pct = (missing / max(n_rows, 1) * 100).round(2)

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = [c for c in df.columns if c not in numeric_cols]

    outliers = {}
    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 4:
            continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_out = int(((series < lo) | (series > hi)).sum())
        if n_out:
            outliers[col] = n_out

    summary_stats = df[numeric_cols].describe().to_dict() if numeric_cols else {}

    correlations = {}
    if len(numeric_cols) >= 2:
        corr = df[numeric_cols].corr(numeric_only=True)
        for i, a in enumerate(numeric_cols):
            for b in numeric_cols[i + 1:]:
                val = corr.loc[a, b]
                if pd.notna(val) and abs(val) >= 0.3:
                    correlations[f"{a}~{b}"] = round(float(val), 3)

    return {
        "path": path,
        "n_rows": n_rows,
        "n_cols": n_cols,
        "columns": list(df.columns),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "numeric_cols": numeric_cols,
        "categorical_cols": categorical_cols,
        "missing_values": {c: int(v) for c, v in missing.items() if v > 0},
        "missing_pct": {c: float(v) for c, v in missing_pct.items() if v > 0},
        "duplicate_rows": int(df.duplicated().sum()),
        "outliers_iqr": outliers,
        "summary_stats": summary_stats,
        "notable_correlations": correlations,
    }
