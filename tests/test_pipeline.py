import os
import sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator_langgraph import run_investigation
from core.state import InvestigationStatus
from tools import dataset_tools, statistics, python_executor


def test_dataset_profile_runs():
    prof = dataset_tools.profile("sample_data/sales.csv")
    assert prof["n_rows"] > 0
    assert "revenue" in prof["numeric_cols"]


def test_ollama_query_posts_to_local_chat_completions(monkeypatch):
    import requests
    from core import llm_client

    request = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "Analyze the revenue trend."}}]}

    def fake_post(url, **kwargs):
        request["url"] = url
        request.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    answer = llm_client.ollama_query("Why did sales fall?")

    assert answer == "Analyze the revenue trend."
    assert request["url"] == "http://localhost:11434/v1/chat/completions"
    assert request["json"] == {
        "model": "llama3",
        "messages": [{"role": "user", "content": "Why did sales fall?"}],
    }
    assert request["timeout"] == (10, 600)


def test_ollama_query_wraps_connection_failure(monkeypatch):
    import requests
    from core import llm_client

    def fail_post(*args, **kwargs):
        raise requests.ConnectionError("Ollama is stopped")

    monkeypatch.setattr(requests, "post", fail_post)
    with pytest.raises(RuntimeError, match="Could not reach Ollama.*Ollama is stopped"):
        llm_client.ollama_query("test")


def test_report_recommends_measured_discount_test_without_llm(monkeypatch):
    from agents import report
    from core.state import Evidence, InvestigationState

    monkeypatch.setenv("OLLAMA_REPORTS", "false")
    state = InvestigationState(question="How can we improve sales?")
    state.add_evidence(Evidence(
        kind="dataset_stat",
        description="Correlation between discount_pct and revenue: r=-0.95",
        payload={"pair": "discount_pct~revenue", "r": -0.95},
    ))

    markdown = report.run(state)

    assert "Sales Improvement Recommendations" in markdown
    assert "controlled test" in markdown
    assert "r=-0.950" in markdown


def test_pdf_includes_evidence_visualizations():
    from io import BytesIO
    from pypdf import PdfReader
    from tools.pdf_export import markdown_to_pdf_bytes

    pdf_bytes = markdown_to_pdf_bytes(
        "# Sales report",
        evidence=[{
            "kind": "dataset_stat",
            "payload": {"pair": "discount_pct~revenue", "r": -0.95},
        }],
    )
    text = " ".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf_bytes)).pages)

    assert "Evidence Visualizations" in text
    assert "discount_pct / revenue" in text
    assert "r = -0.950" in text


def test_correlation_test_computes_real_numbers():
    df = dataset_tools.load("sample_data/sales.csv")
    result = statistics.correlation_test(df, "marketing_spend", "revenue")
    assert "p_value" in result
    assert 0 <= result["p_value"] <= 1


def test_python_executor_captures_output_and_enforces_timeout():
    r = python_executor.run_python("print('hi')", timeout_s=5)
    assert r.status == "ok"
    assert "hi" in r.stdout

    r2 = python_executor.run_python("import time; time.sleep(10)", timeout_s=1)
    assert r2.status == "timeout"


def test_full_investigation_completes_and_finds_decline():
    state = run_investigation(
        "Why did revenue decrease?", ["sample_data/sales.csv"]
    )
    assert state.status == InvestigationStatus.COMPLETED
    assert len(state.hypotheses) >= 1
    decline_hyps = [h for h in state.hypotheses if "decreasing" in h.statement]
    assert decline_hyps, "should detect the genuine declining trend in the sample data"
    assert decline_hyps[0].status == "SUPPORTED"


def test_langgraph_python_tool_node_records_execution():
    state = run_investigation(
        "Why did revenue decrease?",
        ["sample_data/sales.csv"],
        python_code="print('analysis ran')",
    )

    assert state.status == InvestigationStatus.COMPLETED
    assert len(state.tool_log) == 1
    assert state.tool_log[0].tool == "python_executor"
    assert state.tool_log[0].status == "ok"
    assert "analysis ran" in state.tool_log[0].stdout
    assert "Tool executions logged: 1" in state.report_markdown


def test_langgraph_revision_loop_is_bounded():
    """Forcing the critic to always object must not loop forever — budget caps it."""
    import agents.critic as critic_mod
    orig = critic_mod.run
    critic_mod.run = lambda state: False  # always object
    try:
        state = run_investigation("Why did revenue decrease?", ["sample_data/sales.csv"])
        assert state.counters["revision_cycles"] == state.budgets["max_revision_cycles"]
        assert state.status == InvestigationStatus.COMPLETED  # still finishes, doesn't hang
    finally:
        critic_mod.run = orig


def test_pdf_document_retrieval_extracts_real_text():
    """Regression test: retrieval.py used to open every file as raw text,
    which would garble a real PDF's binary content instead of extracting it."""
    from tools.retrieval import retrieval_tfidf
    results = retrieval_tfidf(
        "discounting retention strategy", ["sample_data/customer_success_memo.pdf"], top_k=1
    )
    assert results, "should retrieve a relevant chunk from the PDF"
    assert "discount" in results[0].text.lower()


def test_pgvector_retrieval_embeds_indexes_and_returns_similarity(monkeypatch):
    import sys
    import database
    from types import ModuleType

    from tools import embeddings
    from tools.retrieval import retrieval_pgvector

    indexed = {}
    backend = ModuleType("database.backend")
    backend.BACKEND = "postgres"
    postgres_db = ModuleType("database.postgres_db")
    postgres_db.index_chunks = lambda chunks, sources, vectors: indexed.update(
        chunks=chunks, sources=sources, vectors=vectors
    )
    postgres_db.query_similar = lambda vector, top_k: [
        {"text": "Discount retention evidence", "source": "memo.pdf", "score": 0.91}
    ]
    monkeypatch.setitem(sys.modules, "database.backend", backend)
    monkeypatch.setitem(sys.modules, "database.postgres_db", postgres_db)
    monkeypatch.setattr(database, "postgres_db", postgres_db, raising=False)
    monkeypatch.setattr(embeddings, "embed", lambda texts: [[0.25] * 384 for _ in texts])

    results = retrieval_pgvector(
        "discount retention", ["sample_data/customer_success_memo.pdf"], top_k=1
    )

    assert indexed["chunks"]
    assert indexed["sources"] == ["customer_success_memo.pdf"] * len(indexed["chunks"])
    assert len(indexed["vectors"]) == len(indexed["chunks"])
    assert results[0].text == "Discount retention evidence"
    assert results[0].score == 0.91


def test_retrieval_backend_configuration_dispatches(monkeypatch):
    import sys
    from types import ModuleType
    from tools import retrieval

    monkeypatch.setattr(retrieval, "retrieval_tfidf", lambda query, paths, top_k: ["tfidf"])
    monkeypatch.setattr(retrieval, "retrieval_pgvector", lambda query, paths, top_k: ["pgvector"])

    monkeypatch.setenv("RETRIEVAL_BACKEND", "tfidf")
    assert retrieval.retrieve_documents("query", []) == ["tfidf"]

    backend = ModuleType("database.backend")
    backend.BACKEND = "postgres"
    monkeypatch.setitem(sys.modules, "database.backend", backend)
    monkeypatch.setenv("RETRIEVAL_BACKEND", "pgvector")
    assert retrieval.retrieve_documents("query", []) == ["pgvector"]


def test_postgres_engine_uses_installed_sync_driver():
    from database.postgres_db import engine

    assert engine.dialect.driver == "psycopg2"


def test_critic_blocks_unsupported_hypotheses():
    from core.state import InvestigationState, Hypothesis
    state = InvestigationState(question="test")
    state.hypotheses.append(Hypothesis(statement="X causes Y", status="SUPPORTED"))
    from agents import critic
    may_proceed = critic.run(state)
    assert not may_proceed
    assert any(f.issue == "unsupported_claim" for f in state.critic_findings)
