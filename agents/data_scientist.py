"""
Data Scientist Agent (spec section 6B).

Note on LLM boundary: in the full system, an LLM would decide *which*
columns/relationships are worth investigating given the question. Here
that decision is made with a simple heuristic (keyword match against
column names) so the pipeline runs end-to-end without an API key.
See core/llm_client.py for where to plug a real model in.
"""
from __future__ import annotations
from core.state import InvestigationState, Evidence
from tools import dataset_tools, statistics


def run(state: InvestigationState) -> None:
    state.emit("DataScientist", f"Inspecting {len(state.datasets)} dataset(s)")
    for path in state.datasets:
        try:
            prof = dataset_tools.profile(path)
            df = dataset_tools.load(path)
        except Exception as e:
            state.emit("DataScientist", f"Failed to profile {path}: {e}")
            continue

        # Detect a time column and check each numeric metric for a trend —
        # this is what lets the system directly answer "did X increase/decrease".
        time_col = next((c for c in df.columns if "date" in c.lower() or "time" in c.lower()), None)
        if time_col:
            for metric in prof["numeric_cols"]:
                trend = statistics.trend_over_time(df, time_col, metric)
                if "error" in trend:
                    continue
                if trend["significant_at_0.05"] and abs(trend.get("total_pct_change_first_to_last") or 0) >= 5:
                    state.add_evidence(Evidence(
                        kind="dataset_stat",
                        description=f"{metric} shows a significant {trend['direction']} trend "
                                    f"({trend['total_pct_change_first_to_last']}% first-to-last)",
                        source=path,
                        payload={"trend_metric": metric, **trend},
                        strength=min(trend["r_squared"], 0.9),
                    ))
                    state.emit("DataScientist",
                                f"Trend: {metric} is {trend['direction']} "
                                f"({trend['total_pct_change_first_to_last']}% change, p={trend['p_value']:.4f})")

        state.emit(
            "DataScientist",
            f"{path}: {prof['n_rows']} rows x {prof['n_cols']} cols, "
            f"{len(prof['missing_values'])} cols with missing values, "
            f"{prof['duplicate_rows']} duplicate rows",
        )

        state.add_evidence(Evidence(
            kind="dataset_profile",
            description=f"Data quality profile of {path}",
            source=path,
            payload=prof,
            strength=0.5,
        ))

        for pair, r in prof["notable_correlations"].items():
            state.add_evidence(Evidence(
                kind="dataset_stat",
                description=f"Correlation between {pair.replace('~', ' and ')}: r={r}",
                source=path,
                payload={"pair": pair, "r": r},
                strength=min(abs(r), 0.9),
            ))
            state.emit("DataScientist", f"Notable correlation: {pair} (r={r})")

        if prof["outliers_iqr"]:
            state.emit("DataScientist", f"Outliers detected (IQR method): {prof['outliers_iqr']}")
