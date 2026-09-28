"""
Embedding provider for the pgvector-backed retrieval path.

Tries sentence-transformers (all-MiniLM-L6-v2, 384-dim) first. If model
weights can't be downloaded — for example in a network-restricted environment —
it falls back to a deterministic hashing-based embedding
of the same dimensionality so the rest of the pipeline (pgvector column,
cosine search) still works unchanged. Swap happens transparently: nothing
downstream needs to know which path is active.
"""
from __future__ import annotations
import hashlib
import numpy as np

EMBEDDING_DIM = 384
_model = None
_use_real_model = None


def _try_load_model():
    global _model, _use_real_model
    if _use_real_model is not None:
        return
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        _use_real_model = True
    except Exception:
        _model = None
        _use_real_model = False


def _hash_embed(text: str) -> list[float]:
    """Deterministic fallback: hash-projects words into a fixed-size vector.
    Not semantically meaningful like a real model, but stable and swap-compatible."""
    vec = np.zeros(EMBEDDING_DIM)
    for word in text.lower().split():
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        idx = h % EMBEDDING_DIM
        sign = 1 if (h // EMBEDDING_DIM) % 2 == 0 else -1
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    return (vec / norm if norm > 0 else vec).tolist()


def embed(texts: list[str]) -> list[list[float]]:
    _try_load_model()
    if _use_real_model:
        return _model.encode(texts, normalize_embeddings=True).tolist()
    return [_hash_embed(t) for t in texts]


def using_real_model() -> bool:
    _try_load_model()
    return bool(_use_real_model)
