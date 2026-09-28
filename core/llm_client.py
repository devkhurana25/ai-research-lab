"""Local Ollama Mistral client used by the API and report generation."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def ollama_query(prompt: str) -> str:
    """Send a prompt to Ollama's OpenAI-compatible chat endpoint."""
    return _ollama_complete([{"role": "user", "content": prompt}])


def ollama_chat(messages: list[dict[str, str]]) -> str:
    """Send an existing conversation to local Ollama Mistral."""
    return _ollama_complete(messages)


def _ollama_complete(messages: list[dict[str, str]]) -> str:
    import requests

    base_url = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    try:
        response = requests.post(
            f"{base_url}/v1/chat/completions",
            json={"model": "llama3", "messages": messages},
            timeout=(10, 600),
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach Ollama at {base_url}: {exc}") from exc

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"Ollama request failed ({response.status_code}): {response.text}"
        ) from exc

    try:
        answer = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Ollama returned an unexpected chat-completion response.") from exc
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Ollama returned an empty response.")
    return answer.strip()