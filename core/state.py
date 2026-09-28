"""
Core state models for an investigation.

Design principle (per spec section 2 & 35):
  - Agents communicate through this structured state, not free-form chat.
  - Every conclusion carries a pointer back to the evidence that produced it.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid


class InvestigationStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    DATA_INSPECTION = "DATA_INSPECTION"
    RESEARCH = "RESEARCH"
    HYPOTHESIS_GENERATION = "HYPOTHESIS_GENERATION"
    EXPERIMENTATION = "EXPERIMENTATION"
    CRITIQUE = "CRITIQUE"
    REVISION = "REVISION"
    FINAL_SYNTHESIS = "FINAL_SYNTHESIS"
    REPORT_GENERATION = "REPORT_GENERATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def _id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Evidence:
    id: str = field(default_factory=_id)
    kind: str = ""          # "dataset_stat" | "statistical_test" | "external_source" | "experiment"
    description: str = ""
    source: str = ""        # e.g. "sales.csv:column_correlation" or a URL
    payload: dict = field(default_factory=dict)   # raw numbers so nothing is fabricated
    strength: float = 0.0   # 0-1, derived — never hand-set to an arbitrary "confidence"


@dataclass
class Hypothesis:
    id: str = field(default_factory=_id)
    statement: str = ""
    rationale: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    status: str = "PROPOSED"  # PROPOSED | SUPPORTED | PARTIALLY_SUPPORTED | REJECTED | INSUFFICIENT_EVIDENCE
    confidence: str = "LOW"   # derived, never asserted directly


@dataclass
class CriticFinding:
    id: str = field(default_factory=_id)
    severity: str = "warning"   # "warning" | "blocking"
    target: str = ""             # hypothesis id or finding id being challenged
    issue: str = ""
    detail: str = ""


@dataclass
class ToolExecution:
    id: str = field(default_factory=_id)
    tool: str = ""
    args: dict = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    status: str = "ok"       # ok | error | timeout
    runtime_s: float = 0.0
    artifacts: list[str] = field(default_factory=list)


@dataclass
class InvestigationState:
    id: str = field(default_factory=_id)
    question: str = ""
    status: InvestigationStatus = InvestigationStatus.CREATED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    datasets: list[str] = field(default_factory=list)   # file paths
    plan: list[str] = field(default_factory=list)

    tool_log: list[ToolExecution] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    critic_findings: list[CriticFinding] = field(default_factory=list)

    budgets: dict = field(default_factory=lambda: {
        "max_python_executions": 20,
        "max_revision_cycles": 2,
        "python_execution_timeout_s": 30,
    })
    counters: dict = field(default_factory=lambda: {
        "python_executions": 0,
        "revision_cycles": 0,
    })

    log: list[str] = field(default_factory=list)
    report_markdown: Optional[str] = None
    on_event: Optional[object] = field(default=None, repr=False, compare=False)  # optional callback(actor, message, status) for live streaming

    # Observability (spec section 25): populated by the orchestrator, read by
    # api.py's /admin/stats to compute aggregate metrics across investigations.
    agent_timings_s: dict = field(default_factory=dict)   # {"DataScientist": 0.12, ...}
    total_runtime_s: float = 0.0

    def emit(self, actor: str, message: str) -> None:
        entry = f"[{actor}] {message}"
        self.log.append(entry)
        if self.on_event is not None:
            try:
                self.on_event(actor, message, self.status.value)
            except Exception:
                pass  # streaming is best-effort; never let a broken listener break the investigation

    def add_evidence(self, ev: Evidence) -> str:
        self.evidence.append(ev)
        return ev.id

    def evidence_for(self, ids: list[str]) -> list[Evidence]:
        return [e for e in self.evidence if e.id in ids]
