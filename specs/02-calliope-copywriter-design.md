# Calliope — Self-Learning Copywriter Agent (Iris's first agent)

**Codename:** Calliope *(muse of eloquence, "beautiful-voiced" — sits beside `iris`, `atlas`, `kubera` in the Greek register; alt: `peitho`. Rename freely.)*
**Version:** 0.1
**Date:** 2026-06-23
**Status:** Draft for review
**Author:** Lars + Claude
**Depends on:** `00-iris-vision-and-stack.md`, `01-iris-prototype.md`
**Proves (incrementally):** R8 (persistent identity/memory decoupled from model/host), R9 / §7.5 (self-learning by memory curation), R13 (local-only data boundary). Exercises the full P0 plane model on a single, genuinely useful agent.

---

## 1. Objective

Build **the first real Iris agent**: a copywriter that drafts clear, precise, logically grouped communication (emails and messages) **in Lars's own voice**, and **improves at it over time** by curating its own memory.

This is *not* the full Iris implementation. It is one agent wired as a complete **P0 citizen** (agent card + tier, NATS mailbox, dispatcher-launched ephemeral container, LangGraph router entrypoint, Letta-backed memory), plus the **minimal slice of each plane** needed to run *it* end-to-end on a single host. The mesh demos (tier escalation, cross-machine offline) remain `01-iris-prototype.md`'s job; Calliope's job is to prove the **memory planes** — persistent identity and self-learning — on something touched daily.

The thesis Calliope tests: *an agent's memory can be engineered to learn a person's writing voice in token space, and that improvement is visible and durable across restarts and model swaps.*

## 2. Decisions (locked during brainstorming, 2026-06-23)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | **Substrate** | Full P0 wiring (card+tier, mailbox, dispatcher, router, Letta memory) — minimal slice per plane | First agent should be a true Iris citizen and set the pattern for the rest of the fleet. |
| D2 | **Learning loop** | Seed from a corpus, then learn continuously from draft→edit diffs | The R9 / §7.5 proof; the whole point of the agent. |
| D3 | **Privacy / model** | `local-only`: corpus and drafts never leave the laptop; a local 30B-class model drafts everything; escalation is a no-op for this agent | Honest R13 demonstration. Communication content is privacy-sensitive. |
| D4 | **Seed corpus** | Read-only from `mycelium_prod` read models (emails + messages) via the `readonly` Postgres role / Mycelium MCP server | §11 exactly: Iris agents are read-only consumers of Mycelium. Both registers from one source; stays inside Lars's own infra (not a cloud-vendor leak). |
| D5 | **Front door (NOW)** | CLI + explicit file edit: `calliope write` → draft file → user edits & saves → `calliope learn` ships draft+final → diff → profile update | Deterministic edit signal, simplest, fully local. |
| D6 | **Voice model (NOW)** | Self-editing **style-guide** memory block, rewritten by a periodic **curator subagent** from accumulated diffs | Cleanest R9 demo; the learned artifact is human-readable and debuggable; ports to a Letta core-memory block trivially. |

**Roadmap (explicitly deferred — see §11):** Mycelium-passive learning (auto-diff what was actually sent vs. what was drafted); interactive chat/REPL front door; exemplar/pgvector grounding (richer voice match for the local model); cross-machine deployment (mailbox truly on outpost); multiple voice profiles per register/recipient-type.

## 3. Scope

**In scope (build now):**
- One Letta agent, `calliope`, with a persona block and a self-editing `voice_style_guide` core-memory block.
- One-time **seed** from `mycelium_prod` (sent emails + messages) → initial style guide.
- **Drafting** path: brief or rough draft + style guide → polished draft, on the local model.
- **Learning** path: explicit `calliope learn` captures the draft↔final diff; a curator subagent rewrites the style guide.
- Full P0 plumbing for this one agent on **localhost**, all in containers, model server native (macOS/Metal).
- Automated tests for each acceptance criterion (§9).

**Out of scope (now):** all roadmap items in §2; tier escalation as a live path (Calliope's router always routes local); signed cards / auth / scope attenuation; Temporal; fail-over/circuit-breaker; multiple agents; dashboard/UI; cross-machine split.

## 4. How Calliope maps to the seven planes (§6 of vision)

| Plane | Owner | Calliope's minimal slice |
|---|---|---|
| Identity & State | **Letta** | Agent `calliope`: persona block + `voice_style_guide` block (the learned artifact) + archival store for the diff log. Persists across restarts and model swaps (R8). |
| Orchestration | **LangGraph** | Thin router graph as the entrypoint: `assess → route`. For Calliope, `assess` always yields *within tier* → `route=local`. Built so the pattern holds; escalation edge present but a no-op. |
| Transport | **A2A** | Agent Card at `/.well-known/agent-card.json` with the `x-iris` tier extension. Mailbox endpoint (localhost for P0; outpost later). |
| Durability | **NATS JetStream** | Subjects `iris.tasks.calliope`, `iris.results.<task_id>`, `iris.presence.calliope`. Offline durability falls out of mailbox+dispatcher: stop the dispatcher → tasks queue → restart → drain. |
| Execution | **Local model + dispatcher** | Native MLX/llama.cpp model server on the laptop serves a pinned 30B-class instruct model. The dispatcher launches Calliope's ephemeral container per task; the container reaches the model over the host network. |
| Tools | **MCP** | (a) **Mycelium read-model MCP** (read-only, `readonly` role) for the seed corpus; (b) **filesystem MCP** for reading the brief and writing/reading draft files. |
| Packaging & Isolation | **podman** | Calliope ships as a pinned image (runtime + skills + tools); no host global config mounted. Letta/Postgres/NATS/router/MCP each run as their own container. Model server stays native. |

## 5. Components (isolated units)

Each unit has one purpose, a defined interface, and can be tested independently.

1. **Corpus reader** (`mycelium_read`) — *in:* query (sender = Lars, kind ∈ {email, message}, limit); *out:* normalized `{text, recipient, subject?, sent_at, kind}` records. Read-only over the Mycelium MCP / `readonly` role. **Depends on:** `mycelium_prod` schema (introspected — §12).
2. **Voice analyzer / seeder** (`calliope seed`) — *in:* corpus records; *out:* the initial `voice_style_guide` block. Runs the local model to distill recurring tone, sentence rhythm, salutations/sign-offs, structures-per-recipient-type, banned/favored phrasings. Idempotent (re-seed overwrites a versioned block).
3. **Drafter** (`draft` node) — *in:* `{brief | rough_draft, recipient?, intent?}` + current style guide; *out:* a polished draft. Pure function of (inputs, style guide, model). No memory writes.
4. **CLI caller harness** (`calliope`) — the front door. `write` publishes a task envelope to the mailbox and awaits the result, then writes a **draft file** (`<slug>.draft.md`) with a small front-matter header (task_id, recipient, intent). `learn` reads the **edited file**, pairs it with the stored draft, and publishes a `learn` task. `status` shows the current style-guide version + recent learning activity.
5. **Diff capturer** (`diff` node) — *in:* `{draft, final}`; *out:* a structured `EditRecord` (the textual diff + a model-generated *rationale*: "what changed and the likely stylistic reason"). Appended to the diff log (Letta archival).
6. **Curator subagent** (`curate`) — *in:* accumulated `EditRecord`s since last curation; *out:* a rewritten `voice_style_guide` block (new version). Triggered on a threshold (default: ≥5 new edits) or manually (`calliope learn --curate-now`). This *is* the R9 engine (§7.5: "memory subagents periodically review sessions and rewrite context").
7. **P0 plumbing** — agent card + tier registry entry; mailbox publisher; dispatcher (durable pull consumer that launches the ephemeral container per task and tears it down); router graph; NATS subjects; Letta memory wiring; the pinned container image.

> **Why a separate curator (not per-edit rewrite):** rewriting the style guide on every single edit overfits to one message and thrashes the profile. Batched curation matches the vision's stated mechanism and keeps the learned artifact stable. Each edit is still captured immediately (cheap log append); curation is the deliberate step.

## 6. Data model

**6.1 Agent Card** (served at `/.well-known/agent-card.json`):
```json
{
  "name": "calliope",
  "url": "https://outpost/iris/agents/calliope",   // mailbox (localhost for P0)
  "skills": [{"id": "draft"}, {"id": "learn"}, {"id": "seed"}],
  "x-iris": {
    "model": "<pinned-30b-class-instruct>",
    "tier": "local-general",
    "max_task_class": "writing",
    "node": "laptop",
    "local_only": true
  }
}
```
Tier ladder note: `local-general` sits on the local rung; because `local_only` is set and no higher-tier *writing* specialist is offered, the router never escalates (§10 of vision: `local-only` tasks defer to laptop, never substitute to cloud).

**6.2 Letta memory blocks (intentional, persistent state — §7.6):**
- `persona` — who Calliope is and its operating rules (drafts in Lars's voice, never invents facts, asks when the brief is ambiguous, keeps content local).
- `voice_style_guide` — **the learned artifact.** Human-readable, sectioned: *Tone & register · Sentence rhythm & length · Openings/sign-offs · Structure by recipient-type · Favored phrasings · Phrases to avoid · Formatting habits.* **Versioned** — each curation produces a new version with a one-line changelog; prior versions retained for rollback.
- *(archival)* `edit_log` — the running list of `EditRecord`s, the curator's raw material.

**6.3 `EditRecord`:**
```json
{
  "task_id": "uuid",
  "recipient": "...", "intent": "...",
  "draft": "...", "final": "...",
  "diff": "<unified or token diff>",
  "rationale": "shortened the opening; dropped hedging 'I think'; ...",
  "captured_at": "<stamped by caller>"
}
```

**6.4 Task envelope** (mailbox → NATS → A2A, per §6.3 of prototype):
```json
{
  "task_id": "uuid",
  "to": "calliope",
  "skill": "draft | learn | seed",
  "required_class": "writing",
  "payload": { "...": "skill-specific" },
  "reply_subject": "iris.results.<task_id>",
  "local_only": true,
  "created_at": "<stamped by caller>"
}
```

**6.5 NATS subjects:** `iris.tasks.calliope` (durable, work-queue), `iris.results.<task_id>` (reply), `iris.presence.calliope` (heartbeat). `mycelium_prod` reads go over the MCP/`readonly` role, **not** NATS.

## 7. Flows

**Flow S — seed (one-time / re-runnable):**
1. `calliope seed [--kind email,message] [--limit N]`.
2. Caller publishes a `seed` task; dispatcher launches Calliope's container.
3. Corpus reader pulls Lars's sent records from `mycelium_prod` (read-only).
4. Voice analyzer distills → writes `voice_style_guide` v1 (versioned).
5. Result: a summary of what was learned; the block is inspectable via `calliope status`.

**Flow W — draft (the everyday path):**
1. `calliope write --to "<recipient>" --intent "<what/why>" [--from <rough.md>]`.
2. Caller publishes a `draft` task to the mailbox; returns `working` + `task_id`.
3. Dispatcher launches the ephemeral container; the router `assess`es → `route=local`.
4. Drafter runs the local model with `persona` + `voice_style_guide` + the brief.
5. Result posted to `iris.results.<task_id>`; caller writes `<slug>.draft.md` (with the stored draft retained under `task_id`).

**Flow L — learn (closes the loop):**
1. Lars edits `<slug>.draft.md` and saves; runs `calliope learn <slug>.draft.md`.
2. Caller publishes a `learn` task with `{draft (stored), final (edited file)}`.
3. Diff capturer produces an `EditRecord` (diff + rationale) → appended to `edit_log`.
4. If the edit threshold is reached (or `--curate-now`), the curator subagent reviews accumulated records and writes `voice_style_guide` v(n+1) with a changelog.
5. Result: confirmation + (if curated) the changelog diff between style-guide versions.

**Flow O — offline durability (falls out for free):** stop the dispatcher → `write`/`learn` tasks sit in `iris.tasks.calliope` (verifiable via NATS) → restart the dispatcher → tasks drain, fresh container runs, results returned. Nothing lost. (Same mechanism as prototype Demo B, proven here on localhost by stopping the dispatcher.)

## 8. Error handling & degradation

- **Model server unreachable** — because Calliope is `local-only`, there is **no cloud fail-over** (R13). Retry+backoff against the local server; if still down, the task **stays queued** (defer) until the model is back. Drafting never silently substitutes a cloud model.
- **`mycelium_prod` unreachable** — `seed` and (future) passive learning **defer**; **drafting still works** from the existing `voice_style_guide` (graceful degradation — the learned artifact is local, not dependent on Mycelium at draft time).
- **Bad curation** — style-guide blocks are **versioned with changelogs**; `calliope rollback` restores a prior version. The curator must emit a changelog; an empty/degenerate rewrite is rejected and the prior version kept.
- **Cold start / empty corpus** — `voice_style_guide` begins from a minimal neutral template; drafts are generic until learning accrues. `calliope status` flags "unseeded."
- **Ambiguous brief** — the drafter is instructed (persona) to surface a clarifying question in the result rather than invent facts.

## 9. Test plan (TDD — failing test first, per repo protocol)

| # | Acceptance criterion (observable) |
|---|---|
| **S1** | `calliope seed` on a fixture corpus produces a non-empty, sectioned `voice_style_guide` v1; `status` shows version + source counts. |
| **W1** | `calliope write` returns a draft file; with the model server up, route trace shows `route=local` (no escalation). |
| **L1** | `calliope learn` on an edited draft appends exactly one `EditRecord` (diff + rationale) to `edit_log`. |
| **L2 (R9 core)** | Run a **recurring** draft 3× with a *consistent* edit each time (e.g., always remove a hedging phrase). After curation, assert (a) `voice_style_guide` gained a matching rule, and (b) the **3rd draft needs fewer edits** than the 1st (measurable edit-distance drop). |
| **O1** | With the dispatcher stopped, a `write` task sits in `iris.tasks.calliope` (NATS-verifiable); on restart it drains and returns — nothing lost. |
| **H1 (hermeticity)** | Calliope's image produces the **same draft** for a fixed brief + pinned style guide whether or not the host's global `~/.claude` config exists (per §7.6). |
| **P1 (R8/portability)** | Swap the agent's model binding; `voice_style_guide` and `persona` are unchanged and a draft still runs. |

- **Unit:** corpus-record normalization, diff computation, `EditRecord` (de)serialization, style-guide versioning/rollback, classifier (`required_class=writing` → local), envelope (de)serialization.
- **Integration:** the acceptance table against real Letta + NATS + local model (testcontainers or local compose), each asserting the logged route trace + observable artifact.
- **Regression guard:** for any bug, add a failing test, fix, **revert-to-confirm it catches the regression**, re-apply (per global testing rule). Test fixtures use **anonymized** corpus data — fictional but realistic names/PII.

## 10. Privacy & security

- Every Calliope task carries `local_only: true`; the router/§10-rule guarantees no substitution to a cloud model — defer to laptop instead.
- Mycelium access is the **`readonly` Postgres role** via the MCP read model; Calliope never writes to Mycelium.
- Container mounts **no host global config**; only Letta memory (Postgres) persists between runs (§7.6). The corpus and drafts live only in local Postgres / local files.
- Pinned model + quantization recorded for reproducibility (cloud-API near-determinism is N/A here — local model, so reproducibility is "host + filesystem clean," not bit-identical output, per §7.6 honesty clause).

## 11. Roadmap (deferred; from brainstorming)

| Item | Why later |
|---|---|
| **Mycelium-passive learning** | Auto-diff what Lars *actually sent* (from `mycelium_prod`) against Calliope's stored draft — zero-effort, strongest long-term R9 loop. Needs draft↔sent matching (thread/recipient/time). |
| **Exemplar/pgvector grounding** | Few-shot the local model with retrieved real exemplars for tighter voice match. Adds retrieval infra. |
| **Interactive chat/REPL** | Conversational iteration ("more concise", "drop the apology") with steering logged as signal. |
| **Cross-machine** | Mailbox truly on outpost; Calliope's worker on the laptop — makes offline/durability *fully* real (prototype Demos B/C). |
| **Per-register / per-recipient voice profiles** | Separate style guides for formal email vs. casual chat vs. specific recipients. |

## 12. Open spikes (resolve during build)

- **`mycelium_prod` schema** — introspect the read models: which tables/views hold Lars's **sent** emails and messages, how "sent by Lars" is identified, and how text/recipient/timestamp are exposed. Time-boxed before the corpus reader.
- **A2A ⇄ Letta bridge** — same spike as prototype §12; confirm the clean way to expose `calliope` as an A2A agent.
- **Curation cadence & guardrails** — tune the edit threshold and the "reject degenerate rewrite" check so the style guide improves without thrashing (vision §12 memory-drift risk).
- **Local model pick** — which 30B-class instruct model + quant best matches Lars's voice on the MLX server; pin it.

## 13. Milestones (rough)

| Milestone | Deliverable | Est. |
|---|---|---|
| M0 | Localhost containers (Letta, Postgres, NATS) + native model server reachable from a container; Calliope image builds; agent card served | ~1 session |
| M1 | Corpus reader + `seed` → `voice_style_guide` v1 (**S1, H1**) | ~1 session |
| M2 | Drafting path end-to-end via mailbox+dispatcher+router (**W1, O1**) | ~1–2 sessions |
| M3 | Learn path: diff capture + curator + versioning/rollback (**L1, L2**) — the R9 proof | ~1–2 sessions |
| M4 | Portability + hardening (**P1**), polish CLI (`status`, `rollback`) | ~0.5–1 session |
