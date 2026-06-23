"""Mailbox: publish async tasks to a durable NATS JetStream stream and fetch
results. Tasks survive the dispatcher being offline (§7.3 pull-don't-push).

Two streams: IRIS_TASKS (work-queue, drained by the Go dispatcher) and
IRIS_RESULTS (so a result can be fetched regardless of subscribe timing).
"""

import asyncio
import json

import nats

from calliope.config import Settings

TASKS_STREAM = "IRIS_TASKS"
RESULTS_STREAM = "IRIS_RESULTS"


async def _connect(settings: Settings):
    nc = await nats.connect(settings.nats_url)
    return nc, nc.jetstream()


async def ensure_streams(settings: Settings) -> None:
    nc, js = await _connect(settings)
    try:
        for name, subjects, retention in [
            (TASKS_STREAM, ["iris.tasks.*"], "workqueue"),
            (RESULTS_STREAM, ["iris.results.*"], "limits"),
        ]:
            try:
                await js.add_stream(name=name, subjects=subjects, retention=retention)
            except Exception:
                pass  # already exists
    finally:
        await nc.drain()


async def purge_streams(settings: Settings) -> None:
    nc, js = await _connect(settings)
    try:
        for name in (TASKS_STREAM, RESULTS_STREAM):
            try:
                await js.purge_stream(name)
            except Exception:
                pass
    finally:
        await nc.drain()


async def publish_task(settings: Settings, envelope: dict) -> None:
    nc, js = await _connect(settings)
    try:
        await js.publish(f"iris.tasks.{envelope.get('to', 'calliope')}", json.dumps(envelope).encode())
    finally:
        await nc.drain()


async def tasks_pending(settings: Settings) -> int:
    nc, js = await _connect(settings)
    try:
        info = await js.stream_info(TASKS_STREAM)
        return info.state.messages
    finally:
        await nc.drain()


async def fetch_result(settings: Settings, reply_subject: str, timeout: float = 90.0) -> dict:
    nc, js = await _connect(settings)
    try:
        sub = await js.pull_subscribe(reply_subject, durable=None, stream=RESULTS_STREAM)
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                msgs = await sub.fetch(1, timeout=5)
            except Exception:
                continue
            if msgs:
                await msgs[0].ack()
                return json.loads(msgs[0].data.decode())
        raise TimeoutError(f"no result on {reply_subject} within {timeout}s")
    finally:
        await nc.drain()
