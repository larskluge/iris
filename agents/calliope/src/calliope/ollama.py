"""Direct generation against the native Ollama model server (Metal).

Drafting/translation generation runs here, not through Letta's agentic loop,
so it works reliably with a local model. Memory (persona, voice_style_guide)
is injected by the caller into `system`. Local-only (R13): this only ever
talks to the host Ollama endpoint.
"""

import httpx

from calliope.config import Settings


def generate(
    settings: Settings,
    system: str,
    user: str,
    *,
    num_predict: int = 1024,
    temperature: float = 0.7,
    think: bool = False,
    timeout: float = 180.0,
) -> str:
    """Generate a completion. `think=False` disables Gemma 4's reasoning trace so
    the response is the prose draft itself (a thinking model otherwise spends
    tokens on a `thinking` field and may leave `content` empty)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
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
    return resp.json()["message"]["content"]
