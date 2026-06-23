"""O1 — offline durability: a task published while the dispatcher is down waits
in JetStream and is drained (run in a fresh container) on restart. Nothing lost.

Real NATS + Go dispatcher + agent container. Marked integration."""

import asyncio
import os
import subprocess
import uuid
from pathlib import Path

import pytest

from calliope import mailbox
from calliope.config import Settings

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[3]
DISPATCHER_DIR = REPO / "dispatcher"
DISPATCHER_BIN = DISPATCHER_DIR / "bin" / "dispatcher"


def _ensure_dispatcher_built():
    if not DISPATCHER_BIN.exists():
        subprocess.run(["go", "build", "-o", "bin/dispatcher", "."], cwd=DISPATCHER_DIR, check=True)


def test_offline_durability_o1():
    s = Settings()
    _ensure_dispatcher_built()
    asyncio.run(mailbox.ensure_streams(s))
    asyncio.run(mailbox.purge_streams(s))

    task_id = "o1-" + uuid.uuid4().hex[:8]
    reply = f"iris.results.{task_id}"
    envelope = {
        "task_id": task_id, "to": "calliope", "skill": "draft",
        "payload": {"brief": "Write a one-line hello to Anna confirming the 3pm call."},
        "reply_subject": reply, "local_only": True,
    }

    # Dispatcher DOWN: publish -> the task waits in the durable stream.
    asyncio.run(mailbox.publish_task(s, envelope))
    assert asyncio.run(mailbox.tasks_pending(s)) >= 1, "task should be queued while dispatcher is down"

    # Start the dispatcher -> it drains the queued task in a fresh container.
    proc = subprocess.Popen(
        [str(DISPATCHER_BIN)],
        env={**os.environ, "NATS_URL": s.nats_url, "CALLIOPE_IMAGE": "calliope-agent:latest", "IRIS_NODE": "calliope"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        result = asyncio.run(mailbox.fetch_result(s, reply, timeout=150))
        assert result["task_id"] == task_id
        assert result["result"].strip(), "expected a non-empty draft"
        assert asyncio.run(mailbox.tasks_pending(s)) == 0, "work-queue task should be acked/removed"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
