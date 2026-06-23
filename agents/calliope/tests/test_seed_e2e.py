"""Integration: read the real dev corpus, and seed a style guide end-to-end.

Reads local mycelium_dev (asserts structure only — commits no real data) and
builds/writes a guide from anonymized fixtures. Marked integration.
"""

import pytest

from calliope.config import Settings
from calliope.corpus import read_corpus
from calliope.lettaclient import LettaClient
from calliope.models import CorpusRecord
from calliope.prompts import DEFAULT_PERSONA
from calliope.seed import build_style_guide, seed_agent
from calliope.store import Store

pytestmark = pytest.mark.integration

# Anonymized, fictional corpus (no real third-party PII).
FIXTURE = [
    CorpusRecord(kind="email", text="Hi Anna, confirming the 3pm call tomorrow. Send the agenda when you can. Best, Lars"),
    CorpusRecord(kind="message", text="hey, running 5 min late — start without me"),
    CorpusRecord(kind="message", text="Hallo Max, passt dir morgen um 14 Uhr? Viele Grüße, Lars"),
]


def test_read_corpus_returns_sent_records():
    recs = read_corpus(Settings(), limit=5)
    assert recs, "expected some sent records from mycelium_dev"
    assert all(r.text for r in recs)
    assert {r.kind for r in recs} <= {"email", "message"}


def test_build_guide_has_both_languages():
    guide = build_style_guide(Settings(), FIXTURE)
    assert "## English" in guide and "## German" in guide and "## Shared" in guide


def test_seed_agent_writes_version_one():
    s = Settings()
    letta = LettaClient(s)
    for a in letta.client.agents.list(name="calliope-seed"):
        letta.client.agents.delete(a.id)
    agent = letta.ensure_agent("calliope-seed", persona=DEFAULT_PERSONA, voice_style_guide="placeholder")
    store = Store(s, agent.id)
    store.ensure_schema()
    store.purge()
    try:
        guide = seed_agent(s, letta, agent, store, FIXTURE)
        assert letta.get_block(agent.id, "voice_style_guide") == guide
        assert store.latest_version().version == 1
    finally:
        store.purge()
        letta.delete_agent(agent.id)
