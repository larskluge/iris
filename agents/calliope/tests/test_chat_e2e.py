"""End-to-end chat tests against the real Letta memory + Ollama model.

Basic behaviors of the interactive chat: draft, steer, translate, accept.
Run with services up (`make up`) and the model pulled. Marked integration.
"""

import pytest
from langdetect import detect

pytestmark = pytest.mark.integration


def test_basic_draft(chat_session):
    draft = chat_session.send(
        "Write a short, friendly email to Anna confirming I'll join the 3pm call tomorrow."
    )
    assert draft.strip(), "draft should be non-empty"
    assert chat_session.first_draft == draft
    assert detect(draft) == "en"


def test_steering_revises_draft(chat_session):
    first = chat_session.send(
        "Write a friendly email to Anna confirming the 3pm call and ask her to send the agenda."
    )
    revised = chat_session.send("Make it noticeably shorter and drop the sign-off.")
    assert revised.strip()
    assert revised != first, "steering should change the draft"
    assert chat_session.steering == ["Make it noticeably shorter and drop the sign-off."]


def test_bilingual_translate_preserves_language(chat_session):
    en = chat_session.send("Write two sentences to Anna confirming the 3pm call tomorrow.")
    assert detect(en) == "en"
    de = chat_session.translate("de")
    assert detect(de) == "de", f"expected German, got: {de!r}"
    assert chat_session.lang == "de"


def test_accept_emits_editrecord(chat_session):
    chat_session.send("Write a friendly note to Anna about the 3pm call tomorrow.")
    chat_session.send("Drop any hedging words like 'I think' or 'just'.")
    rec = chat_session.accept()
    assert rec.first_draft.strip() and rec.final.strip()
    assert rec.steering == ["Drop any hedging words like 'I think' or 'just'."]
    assert isinstance(rec.diff, str)
