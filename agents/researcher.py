"""
Research Agent (spec section 6D).

Two evidence sources, both optional:
    1. Locally supplied documents (TF-IDF or pgvector retrieval) -- tried first.
  2. Live web search -- only attempted when local documents didn't already
     answer the question, per spec: "do not perform unnecessary web
     searches for questions answerable entirely from uploaded data."

Web search degrades to zero results rather than failing the investigation
if the network is unavailable (see tools/web_search.py) -- consistent with
the project's "never fabricate evidence" rule.
"""
from __future__ import annotations
from core.state import InvestigationState, Evidence
from tools.retrieval import retrieve_documents
from tools import web_search

MIN_LOCAL_RESULTS_TO_SKIP_WEB_SEARCH = 1


def run(state: InvestigationState, document_paths: list[str]) -> None:
    local_results_found = 0

    if document_paths:
        results = retrieve_documents(state.question, document_paths, top_k=3)
        state.emit("ResearchAgent", f"Retrieved {len(results)} passage(s) from {len(document_paths)} document(s)")
        for r in results:
            state.add_evidence(Evidence(
                kind="external_source",
                description=f"Relevant passage from {r.source} (similarity={r.score:.2f})",
                source=r.source,
                payload={"excerpt": r.text[:400], "similarity": r.score},
                strength=min(r.score, 0.85),
            ))
            state.emit("ResearchAgent", f"Retrieved passage from {r.source} (score={r.score:.2f})")
        local_results_found = len(results)
        if not results:
            state.emit("ResearchAgent", "No sufficiently relevant passages found in supplied documents")
    else:
        state.emit("ResearchAgent", "No documents supplied; skipping document retrieval")

    if local_results_found >= MIN_LOCAL_RESULTS_TO_SKIP_WEB_SEARCH:
        state.emit("ResearchAgent", "Local documents already answer the question; skipping web search")
        return

    state.emit("ResearchAgent", "Attempting web search for external context")
    web_results = web_search.search(state.question, max_results=3)
    if not web_results:
        state.emit("ResearchAgent", "Web search returned no results (unavailable or no results found)")
        return

    for r in web_results:
        state.add_evidence(Evidence(
            kind="external_source",
            description=f"Web result: {r.title}",
            source=r.url,
            payload={"title": r.title, "url": r.url, "snippet": r.snippet[:400]},
            strength=0.4,  # web results get a lower default strength than local, tested evidence
        ))
        state.emit("ResearchAgent", f"Web result: {r.title} ({r.url})")
