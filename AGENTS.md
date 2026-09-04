# AGENTS.md

Notes for agents working in this repo (Iris — a mesh of self-learning agents).

## Layout

- `docs/specs/` — vision + design. Read `02-calliope-copywriter-design.md` before touching Calliope.
- `agents/calliope/` — Calliope agent (host Python 3.14.7, `uv`). See its README.
- `dispatcher/` — Go NATS pull-worker; runs agent tasks in containers.
- `deploy/` — podman compose: Postgres, NATS, Letta.

## Build & test

- Services: `make up` (Postgres + NATS + Letta), `make down`.
- Python: `cd agents/calliope && uv run pytest`. Fast tests: `make test` (`-m "not integration"`). Full suite needs services up + the model: `make test-all`.
- Go: `make go-test`. Agent image: `make image`. Dispatcher: `make dispatcher`.

## Conventions

- TDD: failing test → implement → green. Small, scoped commits.
- Host Python via `uv`, pinned to 3.14.7 (Homebrew); the locked Letta client supports this runtime. The container runtime is configured separately in the Dockerfile.
- Mark service-dependent tests `@pytest.mark.integration`.
- Anonymize committed test data — no real names/PII.
- Commit lock files (`uv.lock`, `go.sum`) on dependency changes.

## Key facts / gotchas

- Model: Ollama `gemma4:31b-mlx` — a *thinking* model; pass `think:false` for prose (`calliope.ollama`).
- Letta is the **memory plane only**; generation runs via **direct Ollama** (local models aren't reliable tool-callers).
- Postgres is on host port **5434** (5433 is mycelium's); pgvector is enabled via an init script.
- Containers reach host services via `host.containers.internal`.
- Everything is `local-only` (R13): no cloud model calls.
