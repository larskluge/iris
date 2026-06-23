"""Read Lars's sent emails/messages from the Mycelium read models (read-only).

Source DSN is configurable (`mycelium_pg_dsn`): local dev DB by default, or
mycelium_prod on outpost (readonly role) for the real seed. We only ever SELECT,
and set the connection read-only as a guardrail. See docs/plans/notes/mycelium-corpus-schema.md.
"""

import psycopg

from calliope.config import Settings
from calliope.models import CorpusRecord

_EMAIL_SQL = """
SELECT subject, coalesce(nullif(body_clean, ''), body_text) AS body, to_addresses, internal_date
FROM emails
WHERE from_address = ANY(%(selves)s)
  AND deleted_at IS NULL
  AND length(coalesce(nullif(body_clean, ''), body_text, '')) BETWEEN 20 AND 4000
ORDER BY internal_date DESC
LIMIT %(limit)s
"""

_MESSAGE_SQL = """
SELECT body, sender_name, sent_at, platform
FROM messages
WHERE sender_name = ANY(%(names)s)
  AND deleted_at IS NULL
  AND length(coalesce(body, '')) BETWEEN 12 AND 2000
ORDER BY sent_at DESC
LIMIT %(limit)s
"""


def _first_recipient(to_addresses) -> str | None:
    """to_addresses is jsonb -> a Python list of strings or {name,address} dicts."""
    if not to_addresses:
        return None
    first = to_addresses[0] if isinstance(to_addresses, list) else to_addresses
    if isinstance(first, dict):
        return first.get("address") or first.get("email") or first.get("name")
    return str(first)


def normalize_email_row(subject, body, to_addresses, internal_date) -> CorpusRecord:
    return CorpusRecord(
        kind="email",
        text=(body or "").strip(),
        subject=subject,
        recipient=_first_recipient(to_addresses),
        sent_at=str(internal_date) if internal_date else None,
    )


def normalize_message_row(body, sender_name, sent_at, platform) -> CorpusRecord:
    return CorpusRecord(
        kind="message",
        text=(body or "").strip(),
        platform=platform,
        sent_at=str(sent_at) if sent_at else None,
    )


def read_corpus(settings: Settings, kinds=("email", "message"), limit: int = 200) -> list[CorpusRecord]:
    records: list[CorpusRecord] = []
    with psycopg.connect(settings.mycelium_pg_dsn) as conn:
        conn.read_only = True  # guardrail: never write to Mycelium
        if "email" in kinds:
            for row in conn.execute(_EMAIL_SQL, {"selves": settings.mycelium_self_emails, "limit": limit}):
                records.append(normalize_email_row(*row))
        if "message" in kinds:
            for row in conn.execute(_MESSAGE_SQL, {"names": settings.mycelium_self_names, "limit": limit}):
                records.append(normalize_message_row(*row))
    return [r for r in records if r.text]
