"""Fast edge-case tests for the chat slice — no services required (fake memory,
dead model endpoint). These cover the 'important edge cases' deterministically."""

import pytest

from calliope.config import Settings
from calliope.errors import EmptyInputError, ModelUnavailableError, NoDraftError
from calliope.session import ChatSession


class FakeLetta:
    def get_block(self, agent_id, label):
        return "PERSONA" if label == "persona" else "STYLE GUIDE"


class FakeAgent:
    id = "agent-fake"


def _session(**overrides):
    return ChatSession(Settings(**overrides), FakeLetta(), FakeAgent())


def test_empty_brief_raises():
    s = _session()
    with pytest.raises(EmptyInputError):
        s.send("   ")


def test_translate_without_draft_raises():
    s = _session()
    with pytest.raises(NoDraftError):
        s.translate("de")


def test_accept_without_draft_raises():
    s = _session()
    with pytest.raises(NoDraftError):
        s.accept()


def test_hand_edit_empty_raises():
    s = _session()
    with pytest.raises(EmptyInputError):
        s.hand_edit("")


def test_model_unreachable_surfaces_clean_error():
    # Point at a dead port: a connection failure must become a friendly typed error,
    # never a raw stack trace or a hang. (R13: no cloud fail-over.)
    s = _session(ollama_base_url="http://localhost:1")
    with pytest.raises(ModelUnavailableError):
        s.send("Write a hello to Anna.")
