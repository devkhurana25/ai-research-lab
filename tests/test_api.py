"""
API-level tests using FastAPI's TestClient (no separate server process needed).
Covers what tests/test_pipeline.py doesn't: HTTP auth, multi-user data
isolation, and the newer endpoints (PDF export, dataset explorer).
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

# Use a dedicated test database so this suite doesn't collide with dev data.
os.environ.setdefault("_TEST_DB_OVERRIDE", "1")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    test_db = tmp_path / "test_lab.db"
    monkeypatch.setattr("database.db.DB_PATH", str(test_db))
    monkeypatch.setattr("core.users.DB_PATH", str(test_db))
    import api
    return TestClient(api.app)


def _register(client, email, password="testpass123"):
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_register_and_duplicate_rejected(client):
    _register(client, "dup@example.com")
    r = client.post("/auth/register", json={"email": "dup@example.com", "password": "testpass123"})
    assert r.status_code == 400


def test_login_wrong_password_rejected(client):
    _register(client, "user@example.com")
    r = client.post("/auth/login", json={"email": "user@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401
    token = _register(client, "me@example.com")
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "me@example.com"


def test_multi_user_investigation_isolation(client):
    token_a = _register(client, "a@example.com")
    token_b = _register(client, "b@example.com")

    r = client.post(
        "/investigations",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"question": "Why did revenue decrease?", "dataset_paths": ["sample_data/sales.csv"]},
    )
    assert r.status_code == 200
    inv_id = r.json()["id"]

    # owner sees it in their list; other user does not
    assert len(client.get("/investigations", headers={"Authorization": f"Bearer {token_a}"}).json()) == 1
    assert len(client.get("/investigations", headers={"Authorization": f"Bearer {token_b}"}).json()) == 0

    # owner can fetch the report; the other user gets 404, not the data
    assert client.get(f"/investigations/{inv_id}/report", headers={"Authorization": f"Bearer {token_a}"}).status_code == 200
    assert client.get(f"/investigations/{inv_id}/report", headers={"Authorization": f"Bearer {token_b}"}).status_code == 404

    # anonymous (no token) must not be able to read an owned investigation either
    assert client.get(f"/investigations/{inv_id}/report").status_code == 404


def test_pdf_export_returns_valid_pdf(client):
    token = _register(client, "pdf@example.com")
    r = client.post(
        "/investigations",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "Why did revenue decrease?", "dataset_paths": ["sample_data/sales.csv"]},
    )
    inv_id = r.json()["id"]
    import api
    api._investigations.pop(inv_id, None)  # exercise persisted evidence after a server restart
    pdf_resp = client.get(f"/investigations/{inv_id}/report.pdf", headers={"Authorization": f"Bearer {token}"})
    assert pdf_resp.status_code == 200
    assert pdf_resp.content[:4] == b"%PDF"
    from io import BytesIO
    from pypdf import PdfReader
    pdf_text = " ".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf_resp.content)).pages)
    assert "Evidence Visualizations" in pdf_text


def test_dataset_explorer_endpoint(client):
    r = client.get("/datasets/profile", params={"path": "sample_data/sales.csv"})
    assert r.status_code == 200
    data = r.json()
    assert data["n_rows"] > 0
    assert "revenue" in data["numeric_cols"]


def test_dataset_explorer_missing_file(client):
    r = client.get("/datasets/profile", params={"path": "sample_data/does_not_exist.csv"})
    assert r.status_code == 404


def test_investigation_stream_emits_worker_failure(client, monkeypatch):
    import api

    def fail_investigation(*args, **kwargs):
        raise RuntimeError("forced investigation failure")

    monkeypatch.setattr(api, "run_investigation", fail_investigation)
    response = client.get(
        "/investigations/stream",
        params={"question": "Why did sales fall?", "dataset_paths": "sample_data/sales.csv"},
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "event: failure" in response.text
    assert "forced investigation failure" in response.text


def test_ollama_query_endpoint_returns_answer(client, monkeypatch):
    import api

    monkeypatch.setattr(api, "ollama_query", lambda prompt: f"Ollama answer: {prompt}")
    response = client.post("/ollama-query", json={"prompt": "Why did sales fall?"})

    assert response.status_code == 200
    assert response.json() == {"answer": "Ollama answer: Why did sales fall?"}


def test_ollama_query_endpoint_returns_service_unavailable(client, monkeypatch):
    import api

    def unavailable(prompt):
        raise RuntimeError("Could not reach Ollama")

    monkeypatch.setattr(api, "ollama_query", unavailable)
    response = client.post("/ollama-query", json={"prompt": "test"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Could not reach Ollama"


def test_chatbot_keeps_bounded_context_between_turns(client, monkeypatch):
    import api
    calls = []

    def answer(messages):
        calls.append(messages)
        return f"Answer {len(calls)}"

    monkeypatch.setattr(api, "ollama_chat", answer)
    first = client.post("/chatbot", json={"prompt": "Why did revenue decrease?"})
    conversation_id = first.json()["conversation_id"]
    second = client.post(
        "/chatbot",
        json={"conversation_id": conversation_id, "prompt": "What if we raise marketing spend?"},
    )

    assert first.status_code == second.status_code == 200
    assert calls[0][0]["role"] == "system"
    assert calls[1][-3:] == [
        {"role": "user", "content": "Why did revenue decrease?"},
        {"role": "assistant", "content": "Answer 1"},
        {"role": "user", "content": "What if we raise marketing spend?"},
    ]
    assert len(second.json()["history"]) == 4


def test_chatbot_includes_investigation_report_as_context(client, monkeypatch):
    import api
    calls = []

    def answer(messages):
        calls.append(messages)
        return "The report suggests testing marketing efficiency."

    monkeypatch.setattr(api, "ollama_chat", answer)
    first = client.post(
        "/chatbot",
        json={"prompt": "How should I improve?", "report_context": "Measured revenue fell 12%."},
    )
    conversation_id = first.json()["conversation_id"]
    client.post("/chatbot", json={"conversation_id": conversation_id, "prompt": "What should I test first?"})

    assert "Measured revenue fell 12%." in calls[0][0]["content"]
    assert "Measured revenue fell 12%." in calls[1][0]["content"]


def test_generate_report_returns_pdf_with_stats_segments_and_ai_findings(client, monkeypatch):
    import api
    prompts = []

    def make_findings(prompt):
        prompts.append(prompt)
        return "Hypotheses\nRevenue may vary by region.\nCritique\nTest this with more evidence.\nProposed actions\nRun a controlled experiment."

    monkeypatch.setattr(api, "ollama_query", make_findings)
    response = client.post("/generate-report", json={
        "dataset_path": "sample_data/sales.csv",
        "report_context": "Investigation found a supported regional revenue difference.",
    })

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert "application/pdf" in response.headers["content-type"]
    from io import BytesIO
    from pypdf import PdfReader
    text = " ".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages)
    assert "Dataset Summary" in text
    assert "mean" in text and "median" in text and "min" in text and "max" in text
    assert "Customer Segmentation and Cohorts" in text
    assert "region" in text
    assert "Hypotheses" in text and "Critique" in text and "Proposed Actions" in text
    assert "Scatter plot" in text
    assert "Investigation found a supported regional revenue difference." in prompts[0]
    assert len(PdfReader(BytesIO(response.content)).pages) >= 6


@pytest.mark.parametrize("payload", [
    {"dataset_json": [
        {"date": "2026-01-01", "region": "East", "revenue": 100, "marketing_spend": 20},
        {"date": "2026-01-02", "region": "West", "revenue": 130, "marketing_spend": 25},
    ]},
    {"csv_data": "date,region,revenue,marketing_spend\n2026-01-01,East,100,20\n2026-01-02,West,130,25"},
])
def test_generate_report_accepts_inline_json_and_csv(client, monkeypatch, payload):
    import api

    monkeypatch.setattr(api, "ollama_query", lambda prompt: "Hypotheses\nCompare regional revenue.")
    response = client.post("/generate-report", json=payload)

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    from io import BytesIO
    from pypdf import PdfReader
    text = " ".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages)
    assert "uploaded" in text
    assert "Dataset Summary" in text
    assert "Executive Summary" in text


def test_generate_report_rejects_missing_or_ambiguous_dataset_input(client):
    missing = client.post("/generate-report", json={})
    ambiguous = client.post("/generate-report", json={
        "dataset_json": [{"revenue": 100}],
        "csv_data": "revenue\n100",
    })

    assert missing.status_code == 400
    assert ambiguous.status_code == 400


def test_generate_report_still_returns_dataset_pdf_when_ollama_is_offline(client, monkeypatch):
    import api

    def unavailable(prompt):
        raise RuntimeError("Could not reach Ollama")

    monkeypatch.setattr(api, "ollama_query", unavailable)
    response = client.post("/generate-report", json={"dataset_path": "sample_data/sales.csv"})

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    from io import BytesIO
    from pypdf import PdfReader
    text = " ".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages)
    assert "Ollama findings unavailable" in text


def test_admin_stats_aggregates_real_data(client):
    assert client.get("/admin/stats").json()["total_investigations"] == 0
    for _ in range(2):
        r = client.post(
            "/investigations",
            json={"question": "Why did revenue decrease?", "dataset_paths": ["sample_data/sales.csv"]},
        )
        assert r.status_code == 200

    stats = client.get("/admin/stats").json()
    assert stats["total_investigations"] == 2
    assert stats["status_breakdown"] == {"COMPLETED": 2}
    assert stats["avg_runtime_s"] is not None and stats["avg_runtime_s"] > 0
    assert "DataScientist" in stats["avg_agent_timings_s"]


def test_admin_stats_include_owned_investigations(client):
    """Regression test: db.get() enforces per-user ownership, and calling it
    with no user_id used to be silently misread as 'anonymous caller blocked
    from an owned investigation', dropping every owned investigation out of
    the admin aggregate entirely. observability.py must use get_any()."""
    from database.db import save

    from core.state import InvestigationState, InvestigationStatus
    state = InvestigationState(question="test")
    state.status = InvestigationStatus.COMPLETED
    state.total_runtime_s = 1.23
    save(state, user_id="some-real-user")

    from core import observability
    stats = observability.compute_stats()
    assert stats["total_investigations"] >= 1
    assert stats["avg_runtime_s"] is not None, (
        "an owned investigation's runtime was dropped from admin stats -- "
        "observability.py must call db.get_any(), not db.get()"
    )
