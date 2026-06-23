"""Letta durability (R8): the agent and its memory survive a Letta restart,
because all state lives in Postgres on a persistent volume."""

import subprocess
import time

import httpx
import pytest

from calliope.config import Settings
from calliope.lettaclient import LettaClient


def _letta_container() -> str:
    out = subprocess.run(
        ["podman", "ps", "--filter", "name=letta", "--format", "{{.Names}}"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert out, "no running letta container found"
    return out[0]


def _wait_health(timeout: int = 60) -> None:
    s = Settings()
    for _ in range(timeout):
        try:
            if httpx.get(f"{s.letta_base_url}/v1/health/", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise AssertionError("letta did not become healthy after restart")


@pytest.mark.integration
def test_agent_and_memory_survive_letta_restart():
    c = LettaClient(Settings())
    agent = c.ensure_agent("calliope-persist", persona="p", voice_style_guide="EN: persist-me")
    aid = agent.id
    try:
        subprocess.run(["podman", "restart", _letta_container()], check=True, capture_output=True)
        _wait_health()
        fresh = LettaClient(Settings())
        assert fresh.get_block(aid, "voice_style_guide") == "EN: persist-me"
    finally:
        LettaClient(Settings()).delete_agent(aid)
