import pytest

from calliope import ollama
from calliope.config import Settings
from calliope.lettaclient import LettaClient


@pytest.mark.integration
def test_letta_memory_roundtrip():
    """Letta stores and updates a core-memory block (the memory plane, R8)."""
    c = LettaClient(Settings())
    agent = c.ensure_agent(
        "calliope-smoke", persona="You reply tersely.", voice_style_guide="EN: terse."
    )
    try:
        c.set_block(agent.id, "voice_style_guide", "EN: warm and concise.")
        assert c.get_block(agent.id, "voice_style_guide") == "EN: warm and concise."
    finally:
        c.delete_agent(agent.id)


@pytest.mark.integration
def test_ollama_generation_nonempty():
    """Direct Ollama generation returns a non-empty completion from the local model."""
    out = ollama.generate(
        Settings(),
        system="You reply with a single short word.",
        user="Reply with the word OK.",
        num_predict=16,
    )
    assert out.strip() != ""
