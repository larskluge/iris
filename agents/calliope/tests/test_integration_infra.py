import socket

import psycopg
import pytest

from calliope.config import Settings


def _port_open(host: str, port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(2)
        return s.connect_ex((host, port)) == 0


@pytest.mark.integration
def test_postgres_reachable():
    s = Settings()
    with psycopg.connect(s.pg_dsn, connect_timeout=3) as conn:
        assert conn.execute("select 1").fetchone()[0] == 1


@pytest.mark.integration
def test_nats_port_open():
    assert _port_open("localhost", 4222)
