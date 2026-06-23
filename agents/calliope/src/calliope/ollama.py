"""Direct generation against the native Ollama model server (Metal).

Drafting/translation generation runs here, not through Letta's agentic loop,
so it works reliably with a local model. Memory (persona, voice_style_guide)
is injected by the caller into `system`. Local-only (R13): this only ever
talks to the host Ollama endpoint.
"""

import httpx

from calliope.config import Settings
from calliope.errors import ModelUnavailableError


def chat(
    settings: Settings,
    messages: list[dict],
    *,
    num_predict: int = 1024,
    temperature: float = 0.7,
    think: bool = False,
    timeout: float = 180.0,
) -> str:
    """Send a full message list (incl. a leading system message) to the local
    Ollama model and return the assistant text.

    `think=False` disables Gemma 4's reasoning trace so the response is the prose
    itself (a thinking model otherwise spends tokens on a `thinking` field and may
    leave `content` empty). Connection/HTTP failures become ModelUnavailableError
    so the REPL can show a clean message instead of a stack trace (R13: no cloud
    fail-over — the caller decides whether to defer or surface)."""
    try:
        resp = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.model,
                "messages": messages,
                "stream": False,
                "think": think,
                "options": {"num_predict": num_predict, "temperature": temperature},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise ModelUnavailableError(
            f"Local model '{settings.model}' is unreachable at {settings.ollama_base_url} ({e})."
        ) from e
    return resp.json()["message"]["content"]


def generate(settings: Settings, system: str, user: str, **kwargs) -> str:
    """Convenience: single system + user turn."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    return chat(settings, messages, **kwargs)
