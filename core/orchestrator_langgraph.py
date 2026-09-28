"""
LangGraph orchestrator (spec section 5, 6A).

The investigation runs as an actual LangGraph StateGraph: explicit nodes, a
conditional revise-or-proceed edge, and a recursion limit as the bounded-
autonomy backstop. An optional Python analysis runs through an isolated tool
node before hypothesis generation.

Each phase's wall-clock time is recorded into state.agent_timings_s (spec
section 25, observability) so /admin/stats can report real per-agent
timing aggregated across investigations, not estimates.
"""
from __future__ import annotations
import time
from pathlib import Path
from typing import TypedDict
from langgraph.graph import StateGraph, END
from core.state import InvestigationState, InvestigationStatus, ToolExecution
from agents import data_scientist, researcher, hypothesis, experiment, ml_experiment, critic, report
from tools.python_executor import run_python


class GraphState(TypedDict):
    state: InvestigationState
    document_paths: list[str]
    python_code: str | None


def _timed(state: InvestigationState, agent_name: str, fn) -> None:
    start = time.time()
    fn()
    elapsed = time.time() - start
    state.agent_timings_s[agent_name] = state.agent_timings_s.get(agent_name, 0.0) + elapsed


def _plan_node(gs: GraphState) -> GraphState:
    s = gs["state"]
    s._start_time = time.time()
    s.emit("Director", f"Investigation created: '{s.question}'")
    s.status = InvestigationStatus.PLANNING
    s.plan = [
        "Inspect datasets", "Retrieve relevant document evidence (if provided)",
        "Generate hypotheses from observed patterns", "Run statistical experiments per hypothesis",
        "Critic review", "Synthesize report",
    ]
    if gs.get("python_code"):
        s.plan.insert(2, "Run optional Python analysis")
    s.emit("Director", f"Plan: {s.plan}")
    return gs


def _inspect_node(gs: GraphState) -> GraphState:
    s = gs["state"]
    s.status = InvestigationStatus.DATA_INSPECTION
    s.emit("Director", "Entering phase: DATA_INSPECTION")
    _timed(s, "DataScientist", lambda: data_scientist.run(s))
    return gs


def _research_node(gs: GraphState) -> GraphState:
    s = gs["state"]
    s.status = InvestigationStatus.RESEARCH
    s.emit("Director", "Entering phase: RESEARCH")
    _timed(s, "ResearchAgent", lambda: researcher.run(s, gs["document_paths"]))
    return gs


def _python_tool_node(gs: GraphState) -> GraphState:
    state = gs["state"]
    code = gs.get("python_code")
    if not code:
        return gs

    timeout_s = state.budgets["python_execution_timeout_s"]
    input_files = {
        f"dataset_{index}{Path(path).suffix}": path
        for index, path in enumerate(state.datasets)
        if Path(path).is_file()
    }
    state.status = InvestigationStatus.EXPERIMENTATION
    state.emit("PythonExecutor", "Running optional analysis in an isolated workspace")

    if state.counters["python_executions"] >= state.budgets["max_python_executions"]:
        status = "error"
        stdout = ""
        stderr = "Python execution budget exhausted"
        runtime_s = 0.0
        artifacts: list[str] = []
    else:
        result = run_python(code, timeout_s=timeout_s, input_files=input_files)
        state.counters["python_executions"] += 1
        status = result.status
        stdout = result.stdout
        stderr = result.stderr
        runtime_s = result.runtime_s
        artifacts = result.artifacts

    state.tool_log.append(ToolExecution(
        tool="python_executor",
        args={"input_files": list(input_files), "timeout_s": timeout_s},
        code=code,
        stdout=stdout,
        stderr=stderr,
        status=status,
        runtime_s=runtime_s,
        artifacts=artifacts,
    ))
    state.emit("PythonExecutor", f"Analysis finished with status: {status}")
    return gs


def _hypothesize_node(gs: GraphState) -> GraphState:
    s = gs["state"]
    s.status = InvestigationStatus.HYPOTHESIS_GENERATION
    s.emit("Director", "Entering phase: HYPOTHESIS_GENERATION")
    s.hypotheses.clear()
    _timed(s, "HypothesisAgent", lambda: hypothesis.run(s))
    return gs


def _experiment_node(gs: GraphState) -> GraphState:
    s = gs["state"]
    s.status = InvestigationStatus.EXPERIMENTATION
    s.emit("Director", "Entering phase: EXPERIMENTATION")
    _timed(s, "ExperimentAgent", lambda: experiment.run(s))
    trend_metrics = [e.payload["trend_metric"] for e in s.evidence if "trend_metric" in e.payload]
    if trend_metrics:
        target = next((m for m in trend_metrics if m.lower() in s.question.lower()), trend_metrics[0])
        _timed(s, "MLExperimentAgent", lambda: ml_experiment.run(s, target))
    return gs


def _critique_node(gs: GraphState) -> GraphState:
    s = gs["state"]
    s.status = InvestigationStatus.CRITIQUE
    s.emit("Director", "Entering phase: CRITIQUE")
    result_holder = {}
    _timed(s, "CriticAgent", lambda: result_holder.__setitem__("v", critic.run(s)))
    s._may_proceed = result_holder["v"]
    return gs


def _revise_node(gs: GraphState) -> GraphState:
    s = gs["state"]
    s.counters["revision_cycles"] += 1
    s.status = InvestigationStatus.REVISION
    s.emit("Director", f"Critic raised blocking issues — starting revision cycle {s.counters['revision_cycles']}")
    s.evidence = [e for e in s.evidence if e.kind in ("dataset_profile", "external_source")]
    s.critic_findings.clear()
    return gs


def _report_node(gs: GraphState) -> GraphState:
    s = gs["state"]
    s.status = InvestigationStatus.FINAL_SYNTHESIS
    s.emit("Director", "Synthesizing final conclusions")
    s.status = InvestigationStatus.REPORT_GENERATION
    s.emit("Director", "Investigation complete")
    s.status = InvestigationStatus.COMPLETED
    _timed(s, "ReportGenerator", lambda: report.run(s))
    s.total_runtime_s = time.time() - getattr(s, "_start_time", time.time())
    # Persistence is the API layer's responsibility (it knows the requesting
    # user, if any) -- see api.py's create_investigation / stream_investigation.
    return gs


def _should_revise(gs: GraphState) -> str:
    s = gs["state"]
    if s._may_proceed:
        return "report"
    if s.counters["revision_cycles"] >= s.budgets["max_revision_cycles"]:
        s.emit("Director", "Revision budget exhausted; proceeding with unresolved critic objections noted in report")
        return "report"
    return "revise"


def _after_research(gs: GraphState) -> str:
    return "python_tool" if gs.get("python_code") else "hypothesize"


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("plan", _plan_node)
    g.add_node("inspect", _inspect_node)
    g.add_node("research", _research_node)
    g.add_node("python_tool", _python_tool_node)
    g.add_node("hypothesize", _hypothesize_node)
    g.add_node("experiment", _experiment_node)
    g.add_node("critique", _critique_node)
    g.add_node("revise", _revise_node)
    g.add_node("report", _report_node)

    g.set_entry_point("plan")
    g.add_edge("plan", "inspect")
    g.add_edge("inspect", "research")
    g.add_conditional_edges(
        "research", _after_research,
        {"python_tool": "python_tool", "hypothesize": "hypothesize"},
    )
    g.add_edge("python_tool", "hypothesize")
    g.add_edge("hypothesize", "experiment")
    g.add_edge("experiment", "critique")
    g.add_conditional_edges("critique", _should_revise, {"report": "report", "revise": "revise"})
    g.add_edge("revise", "hypothesize")  # revision loop
    g.add_edge("report", END)

    return g.compile()


_GRAPH = build_graph()


def run_investigation(
    question: str,
    dataset_paths: list[str],
    document_paths: list[str] | None = None,
    on_event=None,
    python_code: str | None = None,
) -> InvestigationState:
    state = InvestigationState(question=question, datasets=dataset_paths, on_event=on_event)
    result = _GRAPH.invoke(
        {
            "state": state,
            "document_paths": document_paths or [],
            "python_code": python_code,
        },
        config={"recursion_limit": 25},  # bounded-autonomy backstop for the revision loop
    )
    return result["state"]
