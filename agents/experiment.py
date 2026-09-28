"""
Experiment Agent (spec section 6F).

Runs a real statistical test per hypothesis rather than letting the
hypothesis's correlation stand as its own proof — this is what lets
the Critic catch "correlation reused as its own evidence".
"""
from __future__ import annotations
from core.state import InvestigationState, Evidence
from tools import dataset_tools, statistics


def run(state: InvestigationState) -> None:
    state.emit("ExperimentAgent", f"Running experiments for {len(state.hypotheses)} hypothesis(es)")
    for h in state.hypotheses:
        ev = state.evidence_for(h.evidence_ids)
        if not ev:
            continue
        source_path = ev[0].source
        is_trend = "trend_metric" in ev[0].payload

        try:
            df = dataset_tools.load(source_path)
            if is_trend:
                metric = ev[0].payload["trend_metric"]
                time_col = next((c for c in df.columns if "date" in c.lower() or "time" in c.lower()), None)
                result = statistics.trend_over_time(df, time_col, metric) if time_col else {"error": "no time column found"}
                desc = f"Trend re-test: {metric} over {time_col}"
            else:
                pair = ev[0].payload.get("pair", "")
                cols = pair.split("~")
                if len(cols) != 2:
                    continue
                col_a, col_b = cols
                result = statistics.correlation_test(df, col_a, col_b)
                desc = f"Pearson correlation test: {col_a} vs {col_b}"
        except Exception as e:
            result = {"error": str(e)}
            desc = "test failed"

        exp_evidence = Evidence(
            kind="statistical_test",
            description=desc,
            source=source_path,
            payload=result,
            strength=0.0 if "error" in result else (0.8 if result.get("significant_at_0.05") else 0.2),
        )
        state.add_evidence(exp_evidence)
        h.evidence_ids.append(exp_evidence.id)

        strength_label = result.get("strength")  # only present for correlation tests
        if "error" in result:
            h.status = "INSUFFICIENT_EVIDENCE"
            state.emit("ExperimentAgent", f"{h.statement}: could not test ({result['error']})")
        elif result["significant_at_0.05"]:
            h.status = "SUPPORTED" if (strength_label in ("moderate", "strong") or is_trend) else "PARTIALLY_SUPPORTED"
            state.emit("ExperimentAgent", f"{h.statement}: p={result['p_value']:.4f} -> {h.status}")
        else:
            h.status = "REJECTED"
            state.emit("ExperimentAgent", f"{h.statement}: not statistically significant (p={result['p_value']:.4f}) -> REJECTED")

        # confidence derived from evidence, never hand-set
        sig_evidence = [e for e in state.evidence_for(h.evidence_ids) if e.strength >= 0.6]
        h.confidence = "HIGH" if len(sig_evidence) >= 2 else "MODERATE" if len(sig_evidence) == 1 else "LOW"
