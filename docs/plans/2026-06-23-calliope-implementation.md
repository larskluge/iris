# Calliope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Calliope — Iris's first agent — a local-only, self-learning copywriter that drafts emails/messages in Lars's voice (English + German, with in-voice translation) and improves by curating its own memory.

**Architecture:** Letta is the brain — a containerized Letta agent holds identity + memory blocks (`persona`, `voice_style_guide`) + conversation, backed by Postgres, using a native Ollama model (`gemma4:31b-mlx`) over `host.containers.internal:11434`. Humans reach the agent **synchronously** through a Python chat REPL (drafting/translation = Letta messages). Machine/durable work reaches it **asynchronously** through a NATS JetStream mailbox drained by a **Go dispatcher** that launches an ephemeral agent container per task. Learning: an accepted REPL session emits an `EditRecord`; a curator subagent periodically rewrites `voice_style_guide`.

**Tech Stack:** Python 3.12 (via `uv`) for the agent layer (Letta SDK, pydantic, LangGraph, the REPL/CLI, seeder, curator); Go 1.26 for the dispatcher/pull-worker; podman (compose) for Postgres (pgvector) + NATS JetStream + Letta server; Ollama native (Metal) serving Gemma 4 31B; `mycelium_prod` (on outpost, read-only) as the seed corpus.

**Spec:** `specs/02-calliope-copywriter-design.md`. **Depends on:** `specs/00-iris-vision-and-stack.md`, `specs/01-iris-prototype.md`.

---

## Environment (verified 2026-06-23 on u26)

| Tool | State |
|---|---|
| `uv` 0.11.22 | present — pins project Python **3.12.13** (system Python is 3.14, too new for Letta wheels) |
| `go` 1.26.4 | present |
| `podman` 5.8.3 | machine running (applehv, 9 CPU, **8 GiB** RAM, 100 GiB disk); `--add-host` supported |
| `ollama` 0.30.10 | running; **`gemma4:31b-mlx` (20 GB) already pulled** (also `gemma4:26b-mlx`, `gemma4:e4b`) |
| `psql` 18 | client present (server runs in podman) |
| `nats` CLI | **absent** — optional; install via `brew install nats-io/nats-tools/nats` for manual inspection, else use the Python client in tests |
| outpost (mycelium_prod) | reachable: `ssh outpost` works (BatchMode) |

> **Pinned model:** the spec names `gemma4:31b-it-q8_0`; the box already has the Metal-optimized **`gemma4:31b-mlx`**, which the spec lists as the speed-optimized build. This plan uses `gemma4:31b-mlx` (no 34 GB download). Update the spec's card tag to match during M0.3.
> **podman RAM:** 8 GiB holds Postgres + NATS + Letta comfortably (§9 ≈ 2–3.5 GB). If Letta is tight, bump with `podman machine set --memory 12288` (documented in M0.2).

## File structure

```
iris/
  specs/                                  # existing (00, 01, 02)
  docs/plans/2026-06-23-calliope-implementation.md   # this plan
  deploy/
    compose.yaml                          # podman compose: postgres, nats, letta
    nats/nats.conf                        # JetStream config
    .env.example                          # service ports, DSNs, OLLAMA_BASE_URL
  agents/calliope/
    .python-version                       # 3.12
    pyproject.toml                        # uv project
    src/calliope/
      __init__.py
      config.py                           # Settings (pydantic-settings): pg, nats, ollama, model, ssh
      models.py                           # TaskEnvelope, EditRecord, CorpusRecord, StyleGuide
      lettaclient.py                      # thin wrapper: connect, ensure agent, send message, get/set blocks
      corpus.py                           # mycelium_prod reader (SSH tunnel + readonly query)
      seed.py                             # voice analyzer/seeder -> voice_style_guide v1
      draft.py                            # draft/translate helpers (Letta message builders)
      curator.py                          # curator subagent: edit_log -> new style guide version
      signal.py                           # accepted session -> EditRecord
      repl.py                             # interactive chat client (sync to Letta)
      router.py                           # LangGraph assess->local (escalation no-op)
      cli.py                              # `calliope` entrypoint: chat, seed, status, rollback, serve-task
    tests/
      conftest.py                         # fixtures: settings, services, fixture corpus
      test_config.py  test_models.py  test_lettaclient.py
      test_corpus.py  test_seed.py  test_signal.py  test_curator.py
      test_repl.py    test_integration_*.py
    Dockerfile                            # pinned agent image (py3.12 + calliope)
  dispatcher/
    go.mod  go.sum
    main.go                               # NATS pull consumer -> podman run agent image
    envelope.go                           # TaskEnvelope (mirror of models.py)
    envelope_test.go  dispatcher_test.go
  Makefile                                # dev: up, down, test, seed, chat
```

---

## Phase M0 — Infra & scaffolding

Goal: a running localhost control plane (Postgres + NATS + Letta) plus a Letta↔Ollama smoke, the Python package skeleton, and a Go dispatcher skeleton. Outcome: `make up && make test` is green.

### Task 0.1: Python package skeleton + config

**Files:**
- Create: `agents/calliope/.python-version`, `agents/calliope/pyproject.toml`
- Create: `agents/calliope/src/calliope/__init__.py`, `agents/calliope/src/calliope/config.py`
- Test: `agents/calliope/tests/test_config.py`

- [ ] **Step 1: Scaffold the uv project**

```bash
cd /Users/l/code/iris/agents/calliope
echo "3.12" > .python-version
uv init --package --python 3.12 --name calliope .
uv add pydantic pydantic-settings
uv add --dev pytest
```

- [ ] **Step 2: Write the failing test**

`agents/calliope/tests/test_config.py`:
```python
from calliope.config import Settings

def test_settings_defaults():
    s = Settings()
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.model == "gemma4:31b-mlx"
    assert s.pg_dsn.startswith("postgresql://")
    assert s.nats_url.startswith("nats://")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/l/code/iris/agents/calliope && uv run pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: calliope.config`)

- [ ] **Step 4: Implement `config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CALLIOPE_", env_file=".env")
    ollama_base_url: str = "http://localhost:11434"
    model: str = "gemma4:31b-mlx"
    pg_dsn: str = "postgresql://calliope:calliope@localhost:5433/calliope"
    nats_url: str = "nats://localhost:4222"
    letta_base_url: str = "http://localhost:8283"
    # mycelium_prod (read-only) via SSH tunnel — resolved in M1
    mycelium_ssh_host: str = "outpost"
    mycelium_pg_dsn: str = "postgresql://readonly@localhost:6543/mycelium_prod"
```

- [ ] **Step 5: Run test to verify it passes** — `uv run pytest tests/test_config.py -v` → PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/l/code/iris && git add agents/calliope && git commit -m "feat(calliope): python package skeleton + settings"
```

### Task 0.2: Postgres + NATS via podman compose

**Files:**
- Create: `deploy/compose.yaml`, `deploy/nats/nats.conf`, `deploy/.env.example`, `Makefile`
- Test: `agents/calliope/tests/test_integration_infra.py`

- [ ] **Step 1: Write the failing integration test**

`tests/test_integration_infra.py`:
```python
import socket, psycopg, pytest
from calliope.config import Settings

def _port_open(host, port):
    with socket.socket() as s:
        s.settimeout(2); 
        return s.connect_ex((host, port)) == 0

def test_postgres_reachable():
    s = Settings()
    with psycopg.connect(s.pg_dsn, connect_timeout=3) as conn:
        assert conn.execute("select 1").fetchone()[0] == 1

def test_nats_port_open():
    assert _port_open("localhost", 4222)
```
Add deps: `uv add psycopg[binary]`

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/test_integration_infra.py -v` → FAIL (connection refused)

- [ ] **Step 3: Write `deploy/compose.yaml`**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: calliope
      POSTGRES_PASSWORD: calliope
      POSTGRES_DB: calliope
    ports: ["5433:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U calliope"]
      interval: 5s
      retries: 10
  nats:
    image: nats:2.10
    command: ["-js", "-m", "8222"]
    ports: ["4222:4222", "8222:8222"]
volumes:
  pgdata:
```

- [ ] **Step 4: Write `Makefile`**

```make
COMPOSE=podman compose -f deploy/compose.yaml
up: ; $(COMPOSE) up -d
down: ; $(COMPOSE) down
ps: ; $(COMPOSE) ps
test: ; cd agents/calliope && uv run pytest -v
```

- [ ] **Step 5: Bring up and verify**

```bash
cd /Users/l/code/iris && make up
# wait for healthy:
podman compose -f deploy/compose.yaml ps
```
Expected: postgres healthy, nats up. If podman RAM is tight later: `podman machine set --memory 12288 && podman machine stop && podman machine start`.

- [ ] **Step 6: Run tests** — `make test` → the two infra tests PASS

- [ ] **Step 7: Commit**

```bash
git add deploy Makefile agents/calliope && git commit -m "feat(deploy): postgres + nats compose, infra healthcheck tests"
```

### Task 0.3: Letta server + Ollama smoke (critical de-risk)

**Files:**
- Modify: `deploy/compose.yaml` (add `letta` service)
- Create: `agents/calliope/src/calliope/lettaclient.py`
- Test: `agents/calliope/tests/test_lettaclient.py`

- [ ] **Step 1: Add Letta to compose**

```yaml
  letta:
    image: letta/letta:latest
    depends_on: { postgres: { condition: service_healthy } }
    environment:
      LETTA_PG_URI: postgresql://calliope:calliope@postgres:5432/calliope
      OLLAMA_BASE_URL: http://host.containers.internal:11434
    extra_hosts: ["host.containers.internal:host-gateway"]
    ports: ["8283:8283"]
```

- [ ] **Step 2: Write the failing smoke test**

`tests/test_lettaclient.py`:
```python
import pytest
from calliope.lettaclient import LettaClient
from calliope.config import Settings

@pytest.mark.integration
def test_agent_responds_via_ollama():
    c = LettaClient(Settings())
    agent = c.ensure_agent("calliope-smoke", persona="You reply tersely.")
    reply = c.send(agent, "Reply with exactly: OK")
    assert reply.strip() != ""
```
Add dep: `uv add letta-client`  (Letta Python SDK)

- [ ] **Step 3: Run to verify it fails** — FAIL (no `lettaclient`)

- [ ] **Step 4: Implement `lettaclient.py`** (thin wrapper over the Letta SDK)

```python
from letta_client import Letta
from calliope.config import Settings

class LettaClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self.client = Letta(base_url=settings.letta_base_url)

    def ensure_agent(self, name: str, persona: str = ""):
        for a in self.client.agents.list(name=name):
            return a
        return self.client.agents.create(
            name=name,
            model=f"ollama/{self.s.model}",
            embedding="ollama/nomic-embed-text",   # confirm available; else letta default
            memory_blocks=[{"label": "persona", "value": persona}],
        )

    def send(self, agent, text: str) -> str:
        resp = self.client.agents.messages.create(
            agent_id=agent.id,
            messages=[{"role": "user", "content": text}],
        )
        return "".join(m.content for m in resp.messages if getattr(m, "content", None))
```

> **SPIKE NOTE (resolve here, feeds spec §12 "A2A ⇄ Letta bridge"):** confirm the exact Letta SDK surface for this version — model handle format (`ollama/<tag>`), how Ollama is registered, embedding model availability, and the message-response shape. Adjust the wrapper to the real SDK. Warm the model first (`curl .../api/generate` once) — MLX first-load is slow.

- [ ] **Step 5: Run the smoke** — `uv run pytest tests/test_lettaclient.py -m integration -v` → PASS (non-empty reply from Gemma 4)

- [ ] **Step 6: Sync the spec's model tag** — update `specs/02-...` §6.1 card `model` to `gemma4:31b-mlx` (matches the box). Commit spec + code:

```bash
git add agents/calliope deploy specs && git commit -m "feat(calliope): letta server + ollama smoke (gemma4:31b-mlx)"
```

### Task 0.4: Go dispatcher skeleton + envelope

**Files:**
- Create: `dispatcher/go.mod`, `dispatcher/envelope.go`, `dispatcher/envelope_test.go`, `dispatcher/main.go`
- Create: `agents/calliope/src/calliope/models.py` (TaskEnvelope — shared shape)

- [ ] **Step 1: Define the envelope test (Go)**

`dispatcher/envelope_test.go`:
```go
package main
import "testing"
func TestDecodeEnvelope(t *testing.T) {
    j := []byte(`{"task_id":"t1","to":"calliope","skill":"draft","payload":{"brief":"hi"},"local_only":true}`)
    e, err := DecodeEnvelope(j)
    if err != nil { t.Fatal(err) }
    if e.To != "calliope" || e.Skill != "draft" || !e.LocalOnly { t.Fatalf("bad: %+v", e) }
}
```

- [ ] **Step 2: Init module + run failing test**

```bash
cd /Users/l/code/iris/dispatcher && go mod init github.com/lars/iris/dispatcher
go test ./...    # FAIL: DecodeEnvelope undefined
```

- [ ] **Step 3: Implement `envelope.go`**

```go
package main
import "encoding/json"
type Envelope struct {
    TaskID    string                 `json:"task_id"`
    To        string                 `json:"to"`
    Skill     string                 `json:"skill"`
    Payload   map[string]any         `json:"payload"`
    Reply     string                 `json:"reply_subject"`
    LocalOnly bool                   `json:"local_only"`
}
func DecodeEnvelope(b []byte) (*Envelope, error) {
    var e Envelope
    return &e, json.Unmarshal(b, &e)
}
```

- [ ] **Step 4: Run test** — `go test ./...` → PASS

- [ ] **Step 5: Minimal `main.go`** (connect to NATS, log; container-launch lands in M2)

```go
package main
import ("log"; "os"; "github.com/nats-io/nats.go")
func main() {
    url := os.Getenv("NATS_URL"); if url == "" { url = nats.DefaultURL }
    nc, err := nats.Connect(url); if err != nil { log.Fatal(err) }
    defer nc.Close()
    log.Println("dispatcher connected to", url)
}
```
`go get github.com/nats-io/nats.go`

- [ ] **Step 6: Commit**

```bash
cd /Users/l/code/iris && git add dispatcher agents/calliope/src/calliope/models.py && git commit -m "feat(dispatcher): go skeleton + envelope decode"
```

**M0 exit criteria:** `make up` brings up PG+NATS+Letta; `make test` green (config, infra, Letta/Ollama smoke); `go test ./...` green. The two riskiest unknowns (Letta↔Ollama, podman host networking) are proven.

---

## Phase M1 — Corpus + seed (the voice_style_guide v1)

Goal: read Lars's sent EN/DE corpus from `mycelium_prod` (read-only) and distill an initial sectioned, per-language `voice_style_guide`. Proves **S1**, **H1** (partial).

### Task 1.1 (SPIKE): Introspect `mycelium_prod` schema

**Files:** Create `docs/plans/notes/mycelium-corpus-schema.md`

- [ ] **Step 1:** Open a read-only SSH tunnel and introspect:

```bash
ssh outpost "psql mycelium_prod -c '\\dt' -c '\\dv'"   # tables + views
# identify read models holding emails + messages; find Lars's sender id; columns for text, recipient, subject, sent_at, language/direction (sent vs received)
```

- [ ] **Step 2:** Record in `mycelium-corpus-schema.md`: exact table/view names, the "sent by Lars" predicate, and the column mapping → `CorpusRecord{text, recipient, subject?, sent_at, kind, lang?}`. Note whether language is stored or must be detected.
- [ ] **Step 3:** Write 2–3 anonymized fixture rows (fictional names/PII per global rule) into `tests/fixtures/corpus_sample.json` for offline unit tests.
- [ ] **Step 4: Commit** the schema note + fixtures.

> This spike unblocks Task 1.2's exact SQL. Until done, 1.2 uses the fixtures.

### Task 1.2: Corpus reader

**Files:** Create `src/calliope/corpus.py`; Test `tests/test_corpus.py`

- [ ] **Step 1: Failing unit test (against fixtures)**

```python
from calliope.corpus import normalize_rows, CorpusRecord
import json, pathlib

def test_normalize_rows():
    raw = json.loads(pathlib.Path("tests/fixtures/corpus_sample.json").read_text())
    recs = normalize_rows(raw)
    assert all(isinstance(r, CorpusRecord) for r in recs)
    assert recs[0].kind in {"email", "message"}
    assert recs[0].text
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `CorpusRecord` (pydantic) + `normalize_rows()` + `read_corpus(settings, kinds, limit)` (opens SSH local-forward to outpost PG, runs the read-only SELECT from the spike, maps rows). Use `sshtunnel` or `subprocess ssh -L`. Read-only role only.
- [ ] **Step 4:** Run unit test → PASS. (A live `@pytest.mark.integration` test reads N real rows.)
- [ ] **Step 5: Commit.**

### Task 1.3: Voice analyzer / seeder

**Files:** Create `src/calliope/seed.py`, `src/calliope/models.py` (`StyleGuide`); Test `tests/test_seed.py`

- [ ] **Step 1: Failing test** — given fixture corpus, `build_style_guide(records)` returns a `StyleGuide` with non-empty `en` and `de` sections and the standard subsections (tone, rhythm, openings/sign-offs, structure, favored, avoid, formatting).

```python
def test_build_style_guide_has_both_languages():
    sg = build_style_guide(FIXTURE_RECORDS)
    assert sg.en.tone and sg.de.tone
    assert "shared" in sg.model_dump()
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `StyleGuide` model (per-language sections + shared) and `build_style_guide()` — groups records by detected language, prompts the model (via `LettaClient.send` to a transient analyzer agent, or direct Ollama) to distill each section, returns the structured guide. Then `seed_agent(letta, sg)` writes it to the agent's `voice_style_guide` block (versioned: store `v1` + changelog).
- [ ] **Step 4:** Run → PASS (unit uses a stubbed model; an integration test runs the real model on fixtures).
- [ ] **Step 5: Commit.**

### Task 1.4: `calliope seed` + `status` CLI

**Files:** Create `src/calliope/cli.py`; Test `tests/test_cli_seed.py`

- [ ] **Step 1: Failing test** — `calliope status` on a freshly-seeded agent prints the style-guide version and per-language source counts; exit 0.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement a `click`/`typer` CLI: `seed [--kind ...] [--limit N]` (reads corpus → builds guide → writes block), `status` (reads block version + metadata). `uv add typer`.
- [ ] **Step 4:** Run → PASS; manual `uv run calliope seed --limit 200 && uv run calliope status`.
- [ ] **Step 5: Commit.**

**M1 exit criteria (S1):** `calliope seed` produces a non-empty, sectioned `voice_style_guide` v1 with EN+DE sections; `status` shows version + per-language counts.

---

## Phase M2 — Chat REPL + async path

Goal: the everyday interactive front door (sync to Letta) with draft/iterate/`/translate`/`/accept`, plus the async mailbox→dispatcher→ephemeral-container path and offline durability. Proves **W1**, **T1**, **O1**.

> **Spike (spec §12, resolved in M0.3 + here):** with Letta driving conversation directly, P0 can serve the human path entirely through the Letta agent (no A2A needed for sync). A2A is only the *async* card; for P0 the async path can be **NATS-native** (envelope over `iris.tasks.calliope`) with the Agent Card served as a static JSON file. Confirm before building 2.4.

Tasks (each expanded to TDD micro-steps at execution time, once M0.3/M1 land):

- **2.1 Agent definition** — create/ensure the persistent `calliope` Letta agent with `persona` (EN+DE, translate-in-voice, never invent, ask-when-ambiguous, local-only) + the seeded `voice_style_guide`. Test: agent exists with both blocks.
- **2.2 REPL client** (`repl.py`, `cli.py: chat`) — interactive loop bound to the agent: plain message = steer; `/edit` (paste) = hand-edit turn; `/translate <lang>`; `/accept` (hands session to signal capture, M3); `/status`; `/rollback`. Holds transcript client-side. Test (W1): scripted session drafts for an EN brief and the draft reflects a style-guide rule. Test (T1): German brief → German draft; `/translate en` → English preserving voice.
- **2.3 Router** (`router.py`) — LangGraph `assess→route`; for Calliope always `local` (escalation no-op), but built so the trace logs `route=local`. Unit test on the classifier.
- **2.4 Mailbox + async serve** — `cli.py: serve-task` entrypoint (reads an envelope, calls the agent, writes the result); mailbox publisher puts an envelope on `iris.tasks.calliope`. Agent `Dockerfile` (py3.12 + calliope, no host config mounted). Test: `serve-task` on a fixture envelope returns a draft.
- **2.5 Dispatcher container-launch** (`dispatcher/main.go`) — durable JetStream pull consumer on `iris.tasks.calliope`; per task: `podman run --rm <calliope-image> calliope serve-task` with the envelope, capture stdout result, publish to `iris.results.<task_id>`, tear down. Go test with a stub "agent" image.
- **2.6 Offline durability test (O1)** — stop the dispatcher; publish a `draft` task; assert it sits in JetStream (via Python NATS client); start the dispatcher; assert drain + result; nothing lost.

**M2 exit:** W1, T1, O1 green; `calliope chat` is usable end-to-end against the seeded agent.

---

## Phase M3 — Learn loop (the R9 proof)

Goal: capture the accepted-session signal, curate the style guide, version + rollback. Proves **L1**, **L2**.

- **3.1 Signal capturer** (`signal.py`) — accepted session `{first_draft, final, steering[], lang}` → one `EditRecord`; append to Letta archival `edit_log`. Test (L1): one accept → exactly one EditRecord carrying `diff` + `steering`.
- **3.2 Curator subagent** (`curator.py`) — reads accumulated `edit_log` records; prompts the model to rewrite `voice_style_guide` → vN+1 with a one-line changelog; rejects degenerate/empty rewrites (keeps prior). Threshold trigger (default ≥5) + `/learn now`. Test: given 5 records that all say "drop hedging", the new guide gains a matching rule.
- **3.3 Versioning + rollback** — style-guide versions retained; `/rollback` and `calliope rollback` restore a prior version. Test: rollback restores exact prior text.
- **3.4 L2 end-to-end (R9 core)** — 3 sessions for a recurring intent, consistent correction each time; assert (a) guide gained the rule, (b) session 3 needs fewer corrections (edit-distance/steering-count drop).

**M3 exit:** L1, L2 green — Calliope visibly improves.

---

## Phase M4 — Portability + hardening

- **4.1 Model-swap (P1)** — rebind the agent to `gemma4:26b-mlx`; assert `voice_style_guide`/`persona` unchanged and a draft still runs.
- **4.2 Hermeticity (H1)** — a dispatched `draft` task's ephemeral container yields the same draft with/without host `~/.claude` present (no host config mounted).
- **4.3 Error handling** — model down: async defers (stays queued), REPL surfaces error; mycelium down: drafting still works from the existing guide; per §8.
- **4.4 CLI polish + docs** — `status`, `rollback`, README for `make up && calliope seed && calliope chat`.

**M4 exit:** P1, H1 green; full §9 acceptance table passes.

---

## Self-review (against spec §1–§13)

- **R8 (persistent identity/memory):** M0.3 + M2.1 (Letta agent + blocks in Postgres); P1 (4.1). ✓
- **R9 / §7.5 (self-learning):** M3 (signal → curator → versioned guide), L2. ✓
- **R13 (local-only):** Ollama native, no cloud fallback (4.3); mycelium read-only over SSH inside own infra. ✓
- **Front door = chat REPL (D5):** M2.2. ✓  Async path (§4.2): M2.4–2.6. ✓
- **Voice = self-editing style guide (D6):** M1.3 + M3.2. ✓
- **Bilingual + translate (EN/DE):** S1 per-language (M1.3), T1 (M2.2). ✓
- **Polyglot (D7):** Go dispatcher (M0.4, M2.5), Python agent layer. ✓  Boundary = NATS envelope (models.py ↔ envelope.go). ✓
- **Model/runtime (D8):** Ollama + `gemma4:31b-mlx` (M0.3). ✓
- **Corpus from mycelium_prod (D4):** M1.1–1.2 (read-only). ✓
- **Containers/hermeticity (§7.6):** compose services (M0.2/0.3), agent image (M2.4), H1 (4.2). ✓
- **Open spikes (§12):** Mycelium schema (M1.1), Letta/Ollama bridge (M0.3), curation guardrails (M3.2). ✓

**Decomposition honesty:** M0–M1 are fully bite-sized (concrete now). M2–M4 are task-level; their TDD micro-steps are written **at execution time per task** after the M0.3 (Letta SDK shape) and M1.1 (Mycelium schema) spikes resolve — deliberately, to avoid inventing spike-dependent code (which would be placeholders). Each M2–M4 task names its files, goal, and acceptance test.

## Execution order

M0.1 → M0.2 → M0.3 → M0.4 → M1.1 → M1.2 → M1.3 → M1.4 → M2.* → M3.* → M4.*. Commit after every task. Run `make test` + `go test ./...` before each commit.
