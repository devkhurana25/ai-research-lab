"""
Report Generator (spec section 6H / 16).
Every number in the report is read from state.evidence / state.hypotheses —
nothing here is generated freehand.
"""
from __future__ import annotations
import os
from core.state import InvestigationState
from core import llm_client


def _sales_recommendations(state: InvestigationState) -> tuple[str, str]:
    profiles = [e for e in state.evidence if e.kind == "dataset_profile"]
    statistics = [e for e in state.evidence if e.kind == "dataset_stat"]
    measured = []

    for profile in profiles:
        measured.append(
            f"Dataset {profile.source}: {profile.payload.get('n_rows', '?')} rows; "
            f"columns: {', '.join(profile.payload.get('columns', []))}"
        )
    for evidence in statistics:
        measured.append(f"{evidence.description}; measured payload: {evidence.payload}")
    for hypothesis in state.hypotheses:
        measured.append(
            f"Hypothesis ({hypothesis.status}, confidence {hypothesis.confidence}): "
            f"{hypothesis.statement}. Rationale: {hypothesis.rationale}"
        )

    prompt = (
        f"Business question: {state.question}\n\nMeasured dataset evidence:\n"
        + ("\n".join(f"- {item}" for item in measured) or "- No usable dataset evidence")
        + "\n\nGive 3-5 concise, practical experiments to improve sales or revenue. "
        "For each, state the action, the metric to monitor, and a guardrail. "
        "If considering lower prices or discounts, recommend a controlled test, not a blanket change. "
        "Do not invent numbers, claim correlation proves causation, or state unsupported facts. "
        "Clearly distinguish measured evidence from proposed experiments."
    )
    system = (
        "You are a careful sales analyst. Base recommendations only on the supplied evidence. "
        "Prefer measurable, low-risk tests and explicitly note uncertainty."
    )

    if os.getenv("OLLAMA_REPORTS", "false").lower() in {"1", "true", "yes"}:
        try:
            answer = llm_client.ollama_query(f"{system}\n\n{prompt}")
            if answer.strip():
                return answer.strip(), "AI-assisted recommendations; validate with controlled experiments."
        except Exception as exc:
            fallback = _fallback_recommendations(statistics)
            return fallback, f"Ollama recommendations unavailable ({exc}); using measured-data guidance."

    return _fallback_recommendations(statistics), "Ollama report synthesis is disabled; recommendations use measured correlations only."


def _fallback_recommendations(statistics: list) -> str:
    recommendations = []
    for evidence in statistics:
        pair = evidence.payload.get("pair", "")
        correlation = evidence.payload.get("r")
        columns = pair.split("~")
        if len(columns) != 2 or not isinstance(correlation, (int, float)):
            continue
        left, right = columns
        names = {left.lower(), right.lower()}
        if "discount_pct" in names and "revenue" in names and correlation < 0:
            recommendations.append(
                f"Run a controlled test of a modest discount-depth reduction against the current offer; "
                f"discount_pct and revenue are negatively correlated (r={correlation:.3f}). "
                "Compare conversion and net revenue per eligible customer before making a broader change."
            )
        elif "churn_rate" in names and "revenue" in names and correlation < 0:
            recommendations.append(
                f"Pilot a retention intervention for at-risk customers; churn_rate and revenue "
                f"are negatively correlated (r={correlation:.3f}). Track retained revenue and support cost."
            )
    if not recommendations:
        recommendations.append(
            "Run a small, randomized pricing or offer test and compare revenue per eligible customer "
            "against a control group before changing prices broadly."
        )
    recommendations.append(
        "Treat correlations as signals for testing, not proof that changing one metric will cause another to move."
    )
    return "\n".join(f"- {item}" for item in recommendations)


def run(state: InvestigationState) -> str:
    lines = []
    lines.append(f"# Research Report\n")
    lines.append(f"**Question:** {state.question}\n")
    lines.append(f"**Investigation ID:** {state.id}  \n**Status:** {state.status.value}\n")

    lines.append("## Executive Summary\n")
    supported = [h for h in state.hypotheses if h.status in ("SUPPORTED", "PARTIALLY_SUPPORTED")]
    if supported:
        lines.append(
            f"The investigation found {len(supported)} supported or partially supported "
            f"signal(s) relevant to: {state.question}"
        )
        for h in supported:
            lines.append(f"- **{h.statement}** — {h.status} (confidence: {h.confidence})")
    else:
        lines.append("- Insufficient evidence to confidently determine the cause with current data.")
    lines.append("")

    recommendations, recommendation_note = _sales_recommendations(state)
    lines.append("## Sales Improvement Recommendations\n")
    lines.append(recommendations)
    lines.append(f"\n_{recommendation_note}_\n")

    lines.append("## Data Quality\n")
    for e in state.evidence:
        if e.kind == "dataset_profile":
            p = e.payload
            lines.append(f"- `{p['path']}`: {p['n_rows']} rows, {p['n_cols']} cols, "
                          f"{p['duplicate_rows']} duplicate rows, "
                          f"missing values in {list(p['missing_values'].keys()) or 'none'}")
    lines.append("")

    lines.append("## Hypotheses Considered\n")
    if not state.hypotheses:
        lines.append("No hypotheses could be generated from the available data.\n")
    for h in state.hypotheses:
        lines.append(f"### {h.statement}")
        lines.append(f"- Status: **{h.status}**  |  Confidence: **{h.confidence}**")
        lines.append(f"- Rationale: {h.rationale}")
        for e in state.evidence_for(h.evidence_ids):
            lines.append(f"  - Evidence [{e.kind}]: {e.description} — `{e.payload}`")
        lines.append("")

    ml_evidence = [e for e in state.evidence if e.kind == "experiment"]
    if ml_evidence:
        lines.append("## ML Experiments\n")
        for e in ml_evidence:
            lines.append(f"- {e.description}")
            lines.append(f"  - `{e.payload}`")
        lines.append("")

    lines.append("## Critic Review\n")
    if not state.critic_findings:
        lines.append("No issues raised.\n")
    for f in state.critic_findings:
        lines.append(f"- **[{f.severity.upper()}]** {f.issue}: {f.detail}")
    lines.append("")

    lines.append("## Limitations\n")
    lines.append("- Hypotheses are generated from measured dataset signals; recommendations are experiments, not causal conclusions.")
    lines.append("- External/web research is limited to locally supplied documents; no live web search agent yet.\n")

    lines.append("## Methodology & Reproducibility\n")
    lines.append(f"- Datasets analyzed: {state.datasets}")
    lines.append(f"- Tool executions logged: {len(state.tool_log)}")
    lines.append(f"- Revision cycles used: {state.counters['revision_cycles']} / {state.budgets['max_revision_cycles']}")
    lines.append("")

    lines.append("## Investigation Log\n")
    lines.append("```")
    lines.extend(state.log)
    lines.append("```")

    report = "\n".join(lines)
    state.report_markdown = report
    return report
