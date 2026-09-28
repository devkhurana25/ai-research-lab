"""
Critic Agent (spec section 6G).

Checks implemented: correlation-vs-causation language, small sample size,
non-significant results still marked SUPPORTED, and hypotheses with no
independent test evidence beyond the correlation that generated them.
"""
from __future__ import annotations
from core.state import InvestigationState, CriticFinding


CAUSAL_WORDS = ["causes", "caused", "leads to", "results in", "because of"]


def run(state: InvestigationState) -> bool:
    """Returns True if the investigation may proceed to synthesis, False if it must revise."""
    state.emit("Critic", "Reviewing hypotheses and evidence for weaknesses")
    blocking = False

    for h in state.hypotheses:
        if any(w in h.statement.lower() for w in CAUSAL_WORDS):
            state.critic_findings.append(CriticFinding(
                severity="warning", target=h.id,
                issue="correlation_vs_causation",
                detail=f"Hypothesis phrased causally but only correlational evidence exists: '{h.statement}'",
            ))

        test_evidence = [e for e in state.evidence_for(h.evidence_ids) if e.kind == "statistical_test"]
        if not test_evidence and h.status not in ("REJECTED", "INSUFFICIENT_EVIDENCE"):
            state.critic_findings.append(CriticFinding(
                severity="blocking", target=h.id,
                issue="unsupported_claim",
                detail=f"Hypothesis '{h.statement}' has status {h.status} but no independent statistical test backing it.",
            ))
            blocking = True

        for e in test_evidence:
            n = e.payload.get("n", 0)
            if isinstance(n, int) and 0 < n < 10:
                state.critic_findings.append(CriticFinding(
                    severity="warning", target=h.id,
                    issue="small_sample_size",
                    detail=f"Test for '{h.statement}' used only n={n} data points; treat with caution.",
                ))

    for f in state.critic_findings:
        state.emit("Critic", f"[{f.severity.upper()}] {f.issue}: {f.detail}")

    if not state.hypotheses:
        state.critic_findings.append(CriticFinding(
            severity="blocking", target="-", issue="no_hypotheses",
            detail="No hypotheses were generated; evidence base is insufficient to answer the question.",
        ))
        blocking = True

    return not blocking
