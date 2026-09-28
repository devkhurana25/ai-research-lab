"""
Web search tool (spec section 6D: "search external sources when necessary").

Uses duckduckgo-search (no API key required). Honest caveat: this build's
sandbox network policy only allows a fixed list of package registries
(npm, pypi, github, etc) -- it cannot reach duckduckgo.com or any other
live search engine, so this code has NOT been verified against a real
network in this environment. It is written to the same graceful-degradation
pattern as tools/embeddings.py: on any failure (blocked network, timeout,
no results), it returns an empty list rather than raising or fabricating
a result, so the Research Agent's "only search when needed, never invent
sources" rule holds either way.

To verify in a real environment: run
    python -c "from tools.web_search import search; print(search('test query'))"
and confirm it returns real results.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class WebResult:
    title: str
    url: str
    snippet: str


def search(query: str, max_results: int = 3, timeout_s: int = 8) -> list[WebResult]:
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # older package name, kept for compatibility
        except ImportError:
            return []  # neither package installed -- degrade silently, matches embeddings.py's pattern

    try:
        with DDGS(timeout=timeout_s) as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []  # network blocked, rate-limited, or any other failure -- never fabricate a result

    return [
        WebResult(
            title=r.get("title", ""),
            url=r.get("href", r.get("link", "")),
            snippet=r.get("body", r.get("snippet", "")),
        )
        for r in raw
        if r.get("href") or r.get("link")
    ]
