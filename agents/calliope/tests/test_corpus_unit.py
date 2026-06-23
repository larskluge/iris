"""Fast normalization tests with anonymized, fictional rows (no real PII)."""

from calliope.corpus import _first_recipient, normalize_email_row, normalize_message_row


def test_first_recipient_variants():
    assert _first_recipient(["anna@example.com"]) == "anna@example.com"
    assert _first_recipient([{"address": "bob@example.com", "name": "Bob"}]) == "bob@example.com"
    assert _first_recipient([{"name": "Bob"}]) == "Bob"
    assert _first_recipient(None) is None


def test_normalize_email_row():
    r = normalize_email_row("Subject X", "  Hello there.  ", ["anna@example.com"], "2026-01-01 10:00:00")
    assert r.kind == "email"
    assert r.text == "Hello there."
    assert r.subject == "Subject X"
    assert r.recipient == "anna@example.com"
    assert r.sent_at == "2026-01-01 10:00:00"


def test_normalize_message_row():
    r = normalize_message_row("hey, on my way", "Sam", "2026-01-02 09:00:00", "telegram")
    assert r.kind == "message"
    assert r.text == "hey, on my way"
    assert r.platform == "telegram"
