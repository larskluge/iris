# Iris

A mesh of stateful, self-learning agents. See `docs/specs/` for the vision (`00`), the
P0 prototype (`01`), and the first agent (`02`).

## Agents

- **[Calliope](agents/calliope/)** — a local-only, self-learning copywriter: drafts in your voice (EN/DE), learns from your edits.

## Layout

| Path | What |
|---|---|
| `docs/specs/` | vision + design specs |
| `agents/calliope/` | Calliope agent (Python) — see its README |
| `dispatcher/` | Go NATS pull-worker; runs agent tasks in containers |
| `deploy/` | podman compose: Postgres, NATS, Letta |
| `docs/plans/` | implementation plans |

## Run

```bash
make up                                     # control plane (Postgres + NATS + Letta)
cd agents/calliope && uv run calliope chat
```

Full usage: `agents/calliope/README.md`. Contributor/agent notes: `AGENTS.md`.
