"""Postgres-backed persistence for the learning loop, scoped per agent.

Structured records live in the same `calliope` database Letta uses:
- `edit_log`              — accepted-session EditRecords (the curator's raw material)
- `style_guide_versions` — the version history of the voice_style_guide (for rollback)

Both are keyed by `agent_id` so each agent has its own edit signal and version
history. The *current* style guide remains the Letta `voice_style_guide` block
(what drafting reads); this store keeps the history and the edit signal.
"""

import psycopg
from psycopg.types.json import Json

from calliope.config import Settings
from calliope.models import EditRecord, StyleGuideVersion

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS edit_log (
        id          BIGSERIAL PRIMARY KEY,
        agent_id    TEXT NOT NULL,
        lang        TEXT,
        recipient   TEXT,
        intent      TEXT,
        first_draft TEXT NOT NULL,
        final       TEXT NOT NULL,
        diff        TEXT,
        steering    JSONB NOT NULL DEFAULT '[]',
        captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        curated_at  TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS style_guide_versions (
        agent_id   TEXT NOT NULL,
        version    INT NOT NULL,
        value      TEXT NOT NULL,
        changelog  TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (agent_id, version)
    )
    """,
]


class Store:
    def __init__(self, settings: Settings, agent_id: str):
        self.dsn = settings.pg_dsn
        self.agent_id = agent_id

    def _conn(self):
        return psycopg.connect(self.dsn)

    def ensure_schema(self) -> None:
        with self._conn() as c:
            for stmt in _SCHEMA:
                c.execute(stmt)

    # --- edit log -------------------------------------------------------
    def append_edit(self, rec: EditRecord) -> int:
        with self._conn() as c:
            row = c.execute(
                "INSERT INTO edit_log (agent_id, lang, recipient, intent, first_draft, final, diff, steering) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (self.agent_id, rec.lang, rec.recipient, rec.intent, rec.first_draft, rec.final, rec.diff, Json(rec.steering)),
            ).fetchone()
            return row[0]

    def uncurated(self) -> list[EditRecord]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT lang, recipient, intent, first_draft, final, diff, steering "
                "FROM edit_log WHERE agent_id = %s AND curated_at IS NULL ORDER BY id",
                (self.agent_id,),
            ).fetchall()
        return [
            EditRecord(
                lang=r[0], recipient=r[1], intent=r[2],
                first_draft=r[3], final=r[4], diff=r[5] or "", steering=r[6] or [],
            )
            for r in rows
        ]

    def count_uncurated(self) -> int:
        with self._conn() as c:
            return c.execute(
                "SELECT count(*) FROM edit_log WHERE agent_id = %s AND curated_at IS NULL",
                (self.agent_id,),
            ).fetchone()[0]

    def mark_all_curated(self) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE edit_log SET curated_at = now() WHERE agent_id = %s AND curated_at IS NULL",
                (self.agent_id,),
            )

    # --- style-guide versions ------------------------------------------
    def latest_version(self) -> StyleGuideVersion | None:
        with self._conn() as c:
            r = c.execute(
                "SELECT version, value, changelog FROM style_guide_versions "
                "WHERE agent_id = %s ORDER BY version DESC LIMIT 1",
                (self.agent_id,),
            ).fetchone()
        return StyleGuideVersion(version=r[0], value=r[1], changelog=r[2] or "") if r else None

    def get_version(self, version: int) -> StyleGuideVersion | None:
        with self._conn() as c:
            r = c.execute(
                "SELECT version, value, changelog FROM style_guide_versions "
                "WHERE agent_id = %s AND version = %s",
                (self.agent_id, version),
            ).fetchone()
        return StyleGuideVersion(version=r[0], value=r[1], changelog=r[2] or "") if r else None

    def record_version(self, version: int, value: str, changelog: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO style_guide_versions (agent_id, version, value, changelog) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (agent_id, version) DO NOTHING",
                (self.agent_id, version, value, changelog),
            )

    def next_version(self) -> int:
        latest = self.latest_version()
        return (latest.version + 1) if latest else 1

    def purge(self) -> None:
        """Delete this agent's edit log + version history (test/teardown helper)."""
        with self._conn() as c:
            c.execute("DELETE FROM edit_log WHERE agent_id = %s", (self.agent_id,))
            c.execute("DELETE FROM style_guide_versions WHERE agent_id = %s", (self.agent_id,))
