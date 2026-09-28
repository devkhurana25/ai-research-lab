"""
Admin/observability stats (spec section 25).

Aggregates real data already recorded per investigation -- no LLM token
counts or cost estimates, because this build's hypothesis generation is
heuristic, not LLM-driven (see core/llm_client.py), so there's nothing
real to report there yet. What IS real and reported: task completion
rate, per-agent timing, tool/agent failure signals, and revision-cycle
usage -- exactly the categories spec section 25 lists that this system
actually produces.
"""
from __future__ import annotations
from database import backend as db


def compute_stats() -> dict:
    investigations = db.list_all()  # admin view -- intentionally not user-scoped
    total = len(investigations)
    if total == 0:
        return {
            "total_investigations": 0,
            "status_breakdown": {},
            "avg_runtime_s": None,
            "avg_agent_timings_s": {},
            "avg_revision_cycles": None,
            "investigations_with_critic_findings_pct": None,
        }

    status_breakdown: dict[str, int] = {}
    runtimes = []
    agent_timing_totals: dict[str, list[float]] = {}
    revision_cycles = []
    with_critic_findings = 0

    for summary in investigations:
        row = db.get_any(summary["id"])  # admin view bypasses per-user ownership by design
        if not row:
            continue
        status_breakdown[row["status"]] = status_breakdown.get(row["status"], 0) + 1
        detail = row["detail"]

        runtime = detail.get("total_runtime_s")
        if runtime:
            runtimes.append(runtime)

        for agent, seconds in detail.get("agent_timings_s", {}).items():
            agent_timing_totals.setdefault(agent, []).append(seconds)

        revision_cycles.append(detail.get("revision_cycles", 0))

        if detail.get("critic_findings"):
            with_critic_findings += 1

    return {
        "total_investigations": total,
        "status_breakdown": status_breakdown,
        "avg_runtime_s": round(sum(runtimes) / len(runtimes), 3) if runtimes else None,
        "avg_agent_timings_s": {
            agent: round(sum(vals) / len(vals), 4) for agent, vals in agent_timing_totals.items()
        },
        "avg_revision_cycles": round(sum(revision_cycles) / len(revision_cycles), 2) if revision_cycles else None,
        "investigations_with_critic_findings_pct": round(100 * with_critic_findings / total, 1),
    }
