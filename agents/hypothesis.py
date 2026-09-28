"""
Hypothesis Agent (spec section 6E).

Heuristic version: turns correlation/trend evidence into candidate
hypotheses. A real LLM would phrase these more richly and propose
hypotheses not directly implied by a single stat -- that's the extension
point (see core/llm_client.py).

Prioritization matters here: with more than a few numeric columns, every
pairwise correlation blindly turned into a hypothesis produces dozens of
low-value "X associated with Y" statements that bury the ones that
actually answer the question. This agent instead:
  1. Identifies a target column from the question's wording when possible
     (e.g. "revenue" in "why did revenue decrease?").
  2. Always keeps the target's own trend, if any.
  3. Keeps other trends and correlations only when they involve the target,
     ranked by strength, capped at a small number -- signal over volume.
Falls back to ranking everything by strength (still capped) if no target
is identifiable from the question.
"""
from __future__ import annotations
from core.state import InvestigationState, Hypothesis

MAX_HYPOTHESES = 6


def _find_target_column(question: str, stat_evidence: list) -> str | None:
    candidates = set()
    for ev in stat_evidence:
        if "trend_metric" in ev.payload:
            candidates.add(ev.payload["trend_metric"])
        pair = ev.payload.get("pair", "")
        candidates.update(pair.split("~") if pair else [])
    matches = [c for c in candidates if c and c.lower() in question.lower()]
    # Prefer the longest match (e.g. "churn_rate" over a substring false-positive)
    return max(matches, key=len) if matches else None


def run(state: InvestigationState) -> None:
    state.emit("HypothesisAgent", "Generating candidate hypotheses from evidence")
    stat_evidence = [e for e in state.evidence if e.kind == "dataset_stat"]

    if not stat_evidence:
        state.emit("HypothesisAgent", "No strong dataset signals found to hypothesize from")
        return

    target = _find_target_column(state.question, stat_evidence)
    if target:
        state.emit("HypothesisAgent", f"Question appears to be about '{target}' -- prioritizing evidence involving it")

    def relevance(ev) -> tuple[int, float]:
        """Higher is more relevant: (is-target-related, |strength|)."""
        if "trend_metric" in ev.payload:
            involved = ev.payload["trend_metric"] == target
        else:
            involved = target in (ev.payload.get("pair", "").split("~"))
        return (1 if (target and involved) else 0, abs(ev.strength))

    ranked = sorted(stat_evidence, key=relevance, reverse=True)
    # If we found a target, keep only target-relevant evidence plus a couple
    # of the next-strongest signals for context; otherwise just take the top N.
    if target:
        target_related = [e for e in ranked if relevance(e)[0] == 1]
        other = [e for e in ranked if relevance(e)[0] == 0][:2]
        selected = (target_related + other)[:MAX_HYPOTHESES]
    else:
        selected = ranked[:MAX_HYPOTHESES]

    skipped = len(stat_evidence) - len(selected)

    for ev in selected:
        if "trend_metric" in ev.payload:
            metric = ev.payload["trend_metric"]
            statement = f"{metric} has genuinely {ev.payload['direction']} over the observed period"
        else:
            pair = ev.payload.get("pair", "")
            cols = pair.split("~")
            statement = f"{cols[0]} is associated with changes in {cols[1]}" if len(cols) == 2 else ev.description

        h = Hypothesis(
            statement=statement,
            rationale=f"Derived from observed correlation (r={ev.payload.get('r')}) in {ev.source}",
            evidence_ids=[ev.id],
        )
        state.hypotheses.append(h)
        state.emit("HypothesisAgent", f"H: {statement}")

    if skipped > 0:
        state.emit("HypothesisAgent", f"{skipped} weaker/less-relevant signal(s) not raised to hypotheses (kept top {MAX_HYPOTHESES})")

    if not state.hypotheses:
        state.emit("HypothesisAgent", "Insufficient signal to propose any hypothesis")
