"""
Retrieval tool (spec section 9 — RAG for uploaded documents).

Uses scikit-learn TF-IDF + cosine similarity rather than a neural embedding
model + pgvector, because this sandbox has no route to download embedding
model weights. The interface (index_documents / query) is the same shape
a pgvector-backed version would expose, so swapping the implementation
later doesn't require touching any calling code.

Supports .txt/.md (read directly) and .pdf (text extracted via pypdf) --
earlier versions of this file opened every path as raw text, which would
silently garble a real PDF's binary content instead of extracting it.
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass
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

