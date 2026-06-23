"""Data shapes shared across Calliope (and mirrored by the Go dispatcher's envelope)."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EditRecord(BaseModel):
    """The learning signal from one accepted chat session: what the draft became
    (`final`), what was changed (`diff`), and why (`steering`). Curated into the
    voice_style_guide in M3."""

    lang: str = "en"
    recipient: str | None = None
    intent: str | None = None
    first_draft: str
    final: str
    diff: str = ""
    steering: list[str] = Field(default_factory=list)
    captured_at: str = Field(default_factory=_now)


class StyleGuideVersion(BaseModel):
    version: int
    value: str
    changelog: str = ""


class CurationResult(BaseModel):
    version: int
    changelog: str
    changed: bool


class TaskEnvelope(BaseModel):
    """Async task shape (mailbox -> NATS -> dispatcher). Mirrors dispatcher/envelope.go."""

    task_id: str
    to: str = "calliope"
    skill: str = "draft"
    payload: dict = Field(default_factory=dict)
    reply_subject: str | None = None
    local_only: bool = True
    created_at: str = Field(default_factory=_now)
