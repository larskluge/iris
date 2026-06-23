# Calliope

A local-only, self-learning copywriter — Iris's first agent. Drafts emails and
messages in your voice (English + German, with in-voice translation) and improves
over time by curating its own style guide from your edits. Nothing leaves the laptop.

## How it works

- **Memory** — a Letta agent holds the `persona` and a versioned `voice_style_guide` (Postgres).
- **Generation** — direct Ollama on a local model (`gemma4:31b-mlx`); no cloud.
- **Learning** — accepted edits + steering are curated into the style guide (versioned, rollback-able).
- **Two front doors** — an interactive chat (sync to Letta) and an async NATS task path drained by a Go dispatcher that runs each task in a fresh, hermetic container.

## Prerequisites

- `podman`, `uv`, Ollama with `gemma4:31b-mlx` pulled, Go 1.26 (dispatcher only).
- `make up` (from repo root) starts Postgres + NATS + Letta.

## Quickstart

```bash
make up                  # start Postgres + NATS + Letta
cd agents/calliope
uv run calliope seed     # learn your voice from the mycelium corpus
uv run calliope chat     # draft interactively
```

## Commands

| Command | Purpose |
|---|---|
| `calliope chat` | interactive drafting session |
| `calliope seed [--limit N] [--kind email,message]` | seed the style guide from sent mail/messages |
| `calliope learn` | curate the style guide from accepted edits now |
| `calliope rollback <version>` | restore a prior style-guide version |
| `calliope status` | show agent, model, style-guide version |
| `calliope serve-task '<json>'` | process one async envelope (used by the dispatcher) |

### In the chat

| Input | Effect |
|---|---|
| any text | a brief (first turn) or a steering instruction |
| `/translate <lang>` | translate the current draft in-voice (`de`, `en`) |
| `/edit` | paste your own edited version (end with a line `.`) |
| `/accept` | finalize; logs the edit; auto-curates at the threshold |
| `/learn` | curate now |
| `/status` | style-guide version + session info |
| `/quit` | exit |

## Async path (durable / offline)

```bash
make dispatcher          # build the agent image + run the Go dispatcher
```

The dispatcher drains `iris.tasks.calliope`, running each task in a fresh container.
Publish a task with `calliope.mailbox.publish_task`. Tasks queued while the dispatcher
is offline are drained on restart — nothing lost.

## Configuration

Override via `CALLIOPE_`-prefixed env vars (`src/calliope/config.py`):

| Var | Default |
|---|---|
| `CALLIOPE_MODEL` | `gemma4:31b-mlx` |
| `CALLIOPE_OLLAMA_BASE_URL` | `http://localhost:11434` |
| `CALLIOPE_PG_DSN` | `postgresql://calliope:calliope@localhost:5434/calliope` |
| `CALLIOPE_LETTA_BASE_URL` | `http://localhost:8283` |
| `CALLIOPE_NATS_URL` | `nats://localhost:4222` |
| `CALLIOPE_MYCELIUM_PG_DSN` | local `mycelium_dev`; point at `mycelium_prod` (outpost) for the real seed |
| `CALLIOPE_CURATE_THRESHOLD` | `5` |

## Tests

```bash
make test       # fast unit tests (no services)
make test-all   # full suite (needs `make up` + the model)
make go-test    # dispatcher
```
