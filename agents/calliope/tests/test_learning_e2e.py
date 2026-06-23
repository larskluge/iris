"""End-to-end learning loop (R9): edits -> curated style guide -> versioning/rollback.

Real Postgres + Letta + model. Marked integration.
"""

import pytest

from calliope import curator
from calliope.config import Settings
from calliope.lettaclient import LettaClient
from calliope.models import EditRecord
from calliope.prompts import DEFAULT_PERSONA, DEFAULT_STYLE_GUIDE
from calliope.store import Store

pytestmark = pytest.mark.integration


@pytest.fixture
def ctx():
    s = Settings()
    letta = LettaClient(s)
    for a in letta.client.agents.list(name="calliope-learn"):
        letta.client.agents.delete(a.id)
    agent = letta.ensure_agent(
        "calliope-learn", persona=DEFAULT_PERSONA, voice_style_guide=DEFAULT_STYLE_GUIDE
    )
    store = Store(s, agent.id)
    store.ensure_schema()
    store.purge()  # isolate this agent's history
    try:
        yield s, letta, agent, store
    finally:
        store.purge()
        letta.delete_agent(agent.id)


def _hedge_edit() -> EditRecord:
    return EditRecord(
        lang="en",
        first_draft="Hi Anna, I think we should just maybe meet at 3pm?",
        final="Hi Anna, let's meet at 3pm.",
        diff="-I think ... just maybe\n+let's",
        steering=["Drop hedging words like 'I think', 'just', 'maybe'."],
    )


def test_curate_incorporates_repeated_steering(ctx):
    s, letta, agent, store = ctx
    for _ in range(3):
        store.append_edit(_hedge_edit())
    assert store.count_uncurated() == 3

    result = curator.curate(s, letta, agent, store)
    assert result is not None and result.changed
    assert result.version == 2  # v1 = seed, v2 = first curation
    assert result.changelog.strip()

    new_guide = letta.get_block(agent.id, "voice_style_guide").lower()
    assert "hedg" in new_guide or "i think" in new_guide, "guide should encode the hedging rule"
    assert store.count_uncurated() == 0  # edits marked curated


def test_curate_noop_without_edits(ctx):
    s, letta, agent, store = ctx
    assert curator.curate(s, letta, agent, store) is None


def test_curate_skips_no_signal_edits(ctx):
    # A draft accepted as-is (no steering, no diff) carries no signal: acknowledged
    # but must not create a style-guide version.
    s, letta, agent, store = ctx
    store.append_edit(EditRecord(lang="en", first_draft="Same.", final="Same.", diff="", steering=[]))
    assert curator.curate(s, letta, agent, store) is None
    assert store.latest_version() is None
    assert store.count_uncurated() == 0


def test_rollback_restores_previous_guide(ctx):
    s, letta, agent, store = ctx
    original = letta.get_block(agent.id, "voice_style_guide")
    store.append_edit(_hedge_edit())
    curator.curate(s, letta, agent, store)  # -> v2, guide changed
    assert letta.get_block(agent.id, "voice_style_guide") != original

    new_version = curator.rollback(letta, agent, store, target_version=1)
    assert new_version == 3
    assert letta.get_block(agent.id, "voice_style_guide") == original
