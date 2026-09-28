"""
Retrieval tool (spec section 9 — RAG for uploaded documents).

Supports both scikit-learn TF-IDF retrieval and pgvector cosine-similarity
retrieval. Select a backend with RETRIEVAL_BACKEND=tfidf|pgvector|auto;
auto follows the configured database backend.

Supports .txt/.md (read directly) and .pdf (text extracted via pypdf) --
earlier versions of this file opened every path as raw text, which would
silently garble a real PDF's binary content instead of extracting it.
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass
from typing import Literal
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _extract_text(path: str) -> str:
    if path.lower().endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    with open(path, "r", errors="ignore") as f:
        return f.read()


def _chunk(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c for c in chunks if c.strip()]


@dataclass
class RetrievedChunk:
    text: str
    source: str
    score: float


class DocumentIndex:
    def __init__(self):
        self.chunks: list[str] = []
        self.sources: list[str] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None

    def index_documents(self, paths: list[str]) -> int:
        for path in paths:
            if not os.path.exists(path):
                continue
            try:
                text = _extract_text(path)
            except Exception:
                continue  # unreadable/corrupt file -- skip rather than crash the investigation
            for chunk in _chunk(text):
                self.chunks.append(chunk)
                self.sources.append(os.path.basename(path))

        if not self.chunks:
            return 0
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform(self.chunks)
        return len(self.chunks)

    def query(self, question: str, top_k: int = 3) -> list[RetrievedChunk]:
        if not self.chunks or self.vectorizer is None:
            return []
        q_vec = self.vectorizer.transform([question])
        sims = cosine_similarity(q_vec, self.matrix)[0]
        ranked = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:top_k]
        return [
            RetrievedChunk(text=self.chunks[i], source=self.sources[i], score=float(sims[i]))
            for i in ranked if sims[i] > 0
        ]


def retrieval_tfidf(
    query: str, document_paths: list[str] | None = None, top_k: int = 3
) -> list[RetrievedChunk]:
    index = DocumentIndex()
    index.index_documents(document_paths or [])
    return index.query(query, top_k=top_k)


def retrieval_pgvector(
    query: str, document_paths: list[str] | None = None, top_k: int = 3
) -> list[RetrievedChunk]:
    from database.backend import BACKEND
    from database import postgres_db
    from tools.embeddings import embed

    if BACKEND != "postgres":
        raise RuntimeError("pgvector retrieval requires DATABASE_URL to select the Postgres backend")

    chunks: list[str] = []
    sources: list[str] = []
    for path in document_paths or []:
        if not os.path.exists(path):
            continue
        try:
            text = _extract_text(path)
        except Exception:
            continue
        document_chunks = _chunk(text)
        chunks.extend(document_chunks)
        sources.extend([os.path.basename(path)] * len(document_chunks))

    if chunks:
        postgres_db.index_chunks(chunks, sources, embed(chunks))
    matches = postgres_db.query_similar(embed([query])[0], top_k=top_k)
    return [
        RetrievedChunk(
            text=match["text"],
            source=match["source"],
            score=float(match.get("score", 0.0)),
        )
        for match in matches
    ]


def retrieval_backend() -> Literal["tfidf", "pgvector"]:
    configured = os.getenv("RETRIEVAL_BACKEND", "auto").strip().lower()
    if configured == "auto":
        from database.backend import BACKEND

        return "pgvector" if BACKEND == "postgres" else "tfidf"
    if configured not in {"tfidf", "pgvector"}:
        raise ValueError("RETRIEVAL_BACKEND must be 'auto', 'tfidf', or 'pgvector'.")
    if configured == "pgvector":
        from database.backend import BACKEND

        if BACKEND != "postgres":
            raise RuntimeError("RETRIEVAL_BACKEND=pgvector requires DATABASE_URL")
    return configured  # type: ignore[return-value]


def retrieve_documents(
    query: str, document_paths: list[str] | None = None, top_k: int = 3
) -> list[RetrievedChunk]:
    if retrieval_backend() == "pgvector":
        return retrieval_pgvector(query, document_paths, top_k=top_k)
    return retrieval_tfidf(query, document_paths, top_k=top_k)

