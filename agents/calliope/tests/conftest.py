import pytest

from calliope.config import Settings
from calliope.lettaclient import LettaClient
from calliope.prompts import DEFAULT_PERSONA, DEFAULT_STYLE_GUIDE
from calliope.session import ChatSession

try:  # deterministic language detection in tests
    from langdetect import DetectorFactory

    DetectorFactory.seed = 0
except ImportError:  # pragma: no cover
    pass


@pytest.fixture
def chat_session():
    """A ChatSession bound to a fresh real Letta agent (deleted on teardown)."""
    s = Settings()
    letta = LettaClient(s)
    for a in letta.client.agents.list(name="calliope-test"):
        letta.client.agents.delete(a.id)
    agent = letta.ensure_agent(
        "calliope-test", persona=DEFAULT_PERSONA, voice_style_guide=DEFAULT_STYLE_GUIDE
    )
    try:
        yield ChatSession(s, letta, agent)
    finally:
        letta.delete_agent(agent.id)
