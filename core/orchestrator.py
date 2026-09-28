"""
Research Director / Orchestrator (spec section 6A, 11, 12).

Runs the investigation as an explicit, bounded state machine.
Revision loop is capped by state.budgets["max_revision_cycles"] so the
system can never loop forever if the Critic keeps objecting.
"""
from __future__ import annotations
from core.state import InvestigationState, InvestigationStatus
from agents import data_scientist, researcher, hypothesis, experiment, ml_experiment, critic, report


def run_investigation(question: str, dataset_paths: list[str], document_paths: list[str] | None = None) -> InvestigationState:
    document_paths = document_paths or []
    state = InvestigationState(question=question, datasets=dataset_paths)
    state.emit("Director", f"Investigation created: '{question}'")

    state.status = InvestigationStatus.PLANNING
    state.plan = [
        "Inspect datasets",
        "Retrieve relevant document evidence (if provided)",
        "Generate hypotheses from observed patterns",
        "Run statistical experiments per hypothesis",
        "Critic review",
        "Synthesize report",
    ]
    state.emit("Director", f"Plan: {state.plan}")

    state.status = InvestigationStatus.DATA_INSPECTION
    data_scientist.run(state)

    state.status = InvestigationStatus.RESEARCH
    researcher.run(state, document_paths)

    while True:
        state.status = InvestigationStatus.HYPOTHESIS_GENERATION
        state.hypotheses.clear()
        hypothesis.run(state)

        state.status = InvestigationStatus.EXPERIMENTATION
        experiment.run(state)

        trend_metrics = [e.payload["trend_metric"] for e in state.evidence if "trend_metric" in e.payload]
        if trend_metrics:
            target = next((m for m in trend_metrics if m.lower() in state.question.lower()), trend_metrics[0])
            ml_experiment.run(state, target)

        state.status = InvestigationStatus.CRITIQUE
        may_proceed = critic.run(state)

        if may_proceed:
            break

        if state.counters["revision_cycles"] >= state.budgets["max_revision_cycles"]:
            state.emit("Director", "Revision budget exhausted; proceeding with unresolved critic objections noted in report")
            break

        state.counters["revision_cycles"] += 1
        state.status = InvestigationStatus.REVISION
        state.emit("Director", f"Critic raised blocking issues — starting revision cycle {state.counters['revision_cycles']}")
        state.evidence = [e for e in state.evidence if e.kind in ("dataset_profile", "external_source")]
        state.critic_findings.clear()

    state.status = InvestigationStatus.FINAL_SYNTHESIS
    state.emit("Director", "Synthesizing final conclusions")

    state.status = InvestigationStatus.REPORT_GENERATION
    state.emit("Director", "Investigation complete")
    state.status = InvestigationStatus.COMPLETED
    report.run(state)
    # Persistence is left to the caller (see api.py), which knows the
    # requesting user, if any -- keeping the orchestrator user-agnostic.
    return state
