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

Build **the first real Iris agent**: a copywriter that drafts clear, precise, logically grouped communication (emails and messages) **in Lars's own voice — in English and German, and translating between them while preserving that voice** — and **improves at it over time** by curating its own memory.

This is *not* the full Iris implementation. It is one agent wired as a complete **P0 citizen** (agent card + tier, NATS mailbox, dispatcher-launched ephemeral container, LangGraph router entrypoint, Letta-backed memory), plus the **minimal slice of each plane** needed to run *it* end-to-end on a single host. The mesh demos (tier escalation, cross-machine offline) remain `01-iris-prototype.md`'s job; Calliope's job is to prove the **memory planes** — persistent identity and self-learning — on something touched daily.

The thesis Calliope tests: *an agent's memory can be engineered to learn a person's writing voice in token space, and that improvement is visible and durable across restarts and model swaps.*

## 2. Decisions (locked during brainstorming, 2026-06-23)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | **Substrate** | Full P0 wiring (card+tier, mailbox, dispatcher, router, Letta memory) — minimal slice per plane | First agent should be a true Iris citizen and set the pattern for the rest of the fleet. |
| D2 | **Learning loop** | Seed from a corpus, then learn continuously from in-chat steering + hand-edits (the draft→final signal) | The R9 / §7.5 proof; the whole point of the agent. |
| D3 | **Privacy / model** | `local-only`: corpus and drafts never leave the laptop; a local ~31 B model (Gemma 4, D8) drafts everything; escalation is a no-op for this agent | Honest R13 demonstration. Communication content is privacy-sensitive. |
| D4 | **Seed corpus** | Read-only from `mycelium_prod` read models (emails + messages) via the `readonly` Postgres role / Mycelium MCP server | §11 exactly: Iris agents are read-only consumers of Mycelium. Both registers from one source; stays inside Lars's own infra (not a cloud-vendor leak). |
| D5 | **Front door (NOW)** | **Interactive chat/REPL**, synchronous to the Letta agent. A turn is a steering instruction *or* a pasted hand-edit; `/accept` logs final text + steering + first-draft↔final diff as the learning signal. CLI file-edit flow → roadmap. | One natural loop (vs. write→edit→learn); native to Letta's conversational model; captures explicit *why* (steering) **and** *what* (hand-edits) — a superset signal. Sync for low latency; the async/durable path stays for delegation + offline (§4.2). |
| D6 | **Voice model (NOW)** | Self-editing **style-guide** memory block, rewritten by a periodic **curator subagent** from accumulated diffs | Cleanest R9 demo; the learned artifact is human-readable and debuggable; ports to a Letta core-memory block trivially. |
| D7 | **Language (polyglot)** | **Python 3.12** for the agent/LLM/orchestration layer; **Go** for efficiency-critical always-on plumbing (dispatcher/pull-worker now; mailbox + heartbeat are candidates) — see §4.1 | Agents are most reliable in Python and every plane has a first-class Python SDK; Go gives tiny, fast-cold-start binaries for the hot path. Boundary = the NATS envelope (R11), so polyglot adds no architectural complexity. |
| D8 | **Model + runtime** | **Ollama** native on macOS (Metal), pinned to **Gemma 4 31B Dense** (`gemma4:31b-it-q8_0`, or `gemma4:31b-mlx` for speed; `num_ctx 65536`) — see §12 | Strongest confirmed-2026 open model for **German + English + translation**; #3-open on human-preference → natural, non-"AI-ese" prose; native system role aids style-guide adherence; Apache 2.0; fits 128 GB at q8 with room. Dense → consistent voice. |

**Roadmap (explicitly deferred — see §11):** Mycelium-passive learning (auto-diff what was actually sent vs. what was drafted); CLI file-edit front door (batch/non-interactive drafting); exemplar/pgvector grounding (richer voice match — bring forward if Gemma's prose feels flat, §12); cross-machine deployment (mailbox truly on outpost); multiple voice profiles per register/recipient-type.

## 3. Scope

**In scope (build now):**
- One Letta agent, `calliope`, with a persona block and a self-editing `voice_style_guide` core-memory block (with **English and German** sections).
- One-time **seed** from `mycelium_prod` (sent emails + messages, both languages) → initial style guide.
- **Interactive chat/REPL** (sync to the Letta agent): draft, iterate by steering or pasting hand-edits, `/translate` EN↔DE in voice, `/accept` to finalize.
- **Learning** path: `/accept` captures the chat steering + draft↔final diff; a curator subagent rewrites the style guide.
- **Async/durable path** (mailbox → Go dispatcher → ephemeral container) for delegated/offline tasks and the durability test — same agent (§4.2).
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
| Execution | **Local model + Go dispatcher** | Native **Ollama** (Metal) model server on the laptop serves the pinned model; agent containers reach it at `host.containers.internal:11434`. A **Go dispatcher** (§4.1) launches Calliope's ephemeral container per task and tears it down. |
| Tools | **MCP** | (a) **Mycelium read-model MCP** (read-only, `readonly` role) for the seed corpus; (b) **filesystem MCP** for pulling a referenced rough draft / local context file into a chat session. |
| Packaging & Isolation | **podman** | Calliope ships as a pinned image (runtime + skills + tools); no host global config mounted. Letta/Postgres/NATS/router/MCP each run as their own container. Model server stays native. |

### 4.1 Language & runtime split (polyglot)

Python is the default; efficiency-critical, always-on plumbing is **Go from the start**.

- **Python 3.12 — the agent/LLM layer:** Letta memory, the LangGraph router, the drafter/seeder/curator subagent, A2A, MCP. Every plane has a first-class Python SDK and coding agents are most reliable here. Per §9 of the vision a Python process (~50–150 MB) is *noise* beside the model (tens of GB), so its overhead is irrelevant where the agent actually reasons.
- **Go — the hot, always-on plumbing:** the node **dispatcher / NATS pull-worker** (§7.3) — pull a task, launch the agent's container via `podman`, shuttle the result, tear down. A ~10 MB static binary with near-instant cold start and excellent NATS + container libraries; this is where footprint and start latency genuinely matter (one ephemeral container per task). **Candidates (evaluate during M0/M2):** the mailbox endpoint and the presence-heartbeat publisher — keep in Go if the A2A/NATS Go ergonomics stay clean, else Python.
- **Boundary = the NATS task envelope** (§6.4), never shared in-process state. This is exactly R11's language-agnostic seam (the same one that lets Elixir/Mycelium interoperate), so Go ↔ Python only ever exchange envelopes over subjects.

### 4.2 Two front doors (sync human · async machine)

The same `calliope` Letta agent (one identity, one memory, one style guide) is reached two ways, split by concern:

- **Sync — the human REPL.** The interactive chat talks **directly to the Letta agent session** (Letta is conversational and stateful by design): low latency, no per-turn container launch. This is the daily front door and where learning is captured. An exploratory human session is *not* a reproducible delegated task, so the ephemeral-container hermeticity of §7.6 does not apply here.
- **Async — the durable task path.** Delegated, scheduled, or offline work goes **mailbox → Go dispatcher → ephemeral container** (§4.1, §7.3), where per-task hermeticity earns its keep (machine-to-machine reproducibility). This path also proves offline durability (test O1).

Reserving the queue for machine/durable work and letting the human chat hit Letta synchronously is *simpler* than forcing every keystroke through NATS — and it is the correct separation, not a shortcut.

## 5. Components (isolated units)

Each unit has one purpose, a defined interface, and can be tested independently.

1. **Corpus reader** (`mycelium_read`) — *in:* query (sender = Lars, kind ∈ {email, message}, limit); *out:* normalized `{text, recipient, subject?, sent_at, kind}` records. Read-only over the Mycelium MCP / `readonly` role. **Depends on:** `mycelium_prod` schema (introspected — §12).
2. **Voice analyzer / seeder** (`calliope seed`) — *in:* corpus records; *out:* the initial `voice_style_guide` block. Runs the local model to distill recurring tone, sentence rhythm, salutations/sign-offs, structures-per-recipient-type, banned/favored phrasings. Idempotent (re-seed overwrites a versioned block).
3. **Drafter / translator** (`draft` node) — *in:* `{brief | rough_draft, recipient?, intent?, target_lang?}` + current style guide; *out:* a polished draft, or an in-voice EN↔DE **translation** when `target_lang` is set (translation reads the style guide too, so it preserves voice rather than rendering literal). Pure function of (inputs, style guide, model). No memory writes.
4. **REPL client** (`calliope chat`) — the front door. An interactive session bound to the Letta agent (sync, §4.2). A plain message = a steering instruction; `/edit` (or pasting a revised version) = a hand-edit turn; `/translate <lang>` = translate the current draft in-voice; `/accept` = finalize and emit the learning signal (final text + steering trajectory + first-draft↔final diff); `/status` shows the style-guide version + recent learning; `/rollback` reverts a version. Holds the conversation transcript client-side.
5. **Signal capturer** (`diff` node) — *in:* `{first_draft, final, steering[]}` from an accepted session; *out:* a structured `EditRecord` — the textual draft↔final diff (the *what*) **plus** the explicit steering instructions (the *why*, near-verbatim style rules) and a model-generated rationale. Appended to the diff log (Letta archival).
6. **Curator subagent** (`curate`) — *in:* accumulated `EditRecord`s since last curation; *out:* a rewritten `voice_style_guide` block (new version). Triggered on a threshold (default: ≥5 new edits) or manually (`calliope learn --curate-now`). This *is* the R9 engine (§7.5: "memory subagents periodically review sessions and rewrite context").
7. **P0 plumbing** — agent card + tier registry entry; mailbox publisher; **Go dispatcher** (§4.1 — durable pull consumer that launches the ephemeral container per task and tears it down); router graph; NATS subjects; Letta memory wiring; the pinned container image.

> **Why a separate curator (not per-edit rewrite):** rewriting the style guide on every single edit overfits to one message and thrashes the profile. Batched curation matches the vision's stated mechanism and keeps the learned artifact stable. Each edit is still captured immediately (cheap log append); curation is the deliberate step.

## 6. Data model

**6.1 Agent Card** (served at `/.well-known/agent-card.json`):
```json
{
  "name": "calliope",
  "url": "https://outpost/iris/agents/calliope",   // mailbox (localhost for P0)
  "skills": [{"id": "draft"}, {"id": "translate"}, {"id": "learn"}, {"id": "seed"}],
  "x-iris": {
    "model": "gemma4:31b-mlx",
    "tier": "local-general",
    "max_task_class": "writing",
    "languages": ["en", "de"],
    "node": "laptop",
    "local_only": true
  }
}
```
Tier ladder note: `local-general` sits on the local rung; because `local_only` is set and no higher-tier *writing* specialist is offered, the router never escalates (§10 of vision: `local-only` tasks defer to laptop, never substitute to cloud).

**6.2 Letta memory blocks (intentional, persistent state — §7.6):**
- `persona` — who Calliope is and its operating rules (drafts in Lars's voice in **English and German**, translates EN↔DE preserving voice, never invents facts, asks when the brief is ambiguous, keeps content local).
- `voice_style_guide` — **the learned artifact.** Human-readable, sectioned: *Tone & register · Sentence rhythm & length · Openings/sign-offs · Structure by recipient-type · Favored phrasings · Phrases to avoid · Formatting habits.* Sections are kept **per language (English / German)** since register and idiom differ, plus a shared section for language-independent habits. **Versioned** — each curation produces a new version with a one-line changelog; prior versions retained for rollback.
- *(archival)* `edit_log` — the running list of `EditRecord`s, the curator's raw material.

**6.3 `EditRecord`:**
```json
{
  "session_id": "uuid",
  "recipient": "...", "intent": "...", "lang": "en | de",
  "first_draft": "...", "final": "...",
  "diff": "<unified or token diff>",
  "steering": ["make it more concise", "drop the apology", "use 'Hi' not 'Dear'"],
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

**Flow W — chat draft & iterate (the everyday path, sync §4.2):**
1. `calliope chat` opens a session bound to the Letta agent.
2. Lars: "Draft a reply to `<recipient>` about `<intent>`" (in EN or DE).
3. Agent drafts with `persona` + `voice_style_guide` + the conversation; replies in-session (low latency, no container launch).
4. Lars iterates: steering ("more concise", "drop the apology") and/or `/edit` to paste a hand-edited version; `/translate de` renders the current draft in German, in voice.
5. `/accept` → final text is returned and the session's `{first_draft, final, steering[], lang}` is handed to the signal capturer.

**Flow L — learn / curate (closes the loop):**
1. On `/accept`, the signal capturer writes one `EditRecord` (diff + steering + rationale) to `edit_log`.
2. When the threshold is reached (default ≥5 records) or on `/learn now`, the curator subagent reviews accumulated records and writes `voice_style_guide` v(n+1) with a changelog. Steering maps near-directly to rules; diffs catch the unspoken habits.
3. The next session's drafts reflect the new version. `/status` shows the version + changelog.

**Flow O — offline durability (async path, §4.2; falls out for free):** a delegated `draft` task published to the mailbox while the dispatcher is stopped sits in `iris.tasks.calliope` (verifiable via NATS) → restart the dispatcher → it drains, a fresh ephemeral container runs, result returned. Nothing lost. (Same mechanism as prototype Demo B; proven on localhost by stopping the dispatcher. The interactive REPL is sync and not subject to this path.)

## 8. Error handling & degradation

- **Model server unreachable** — because Calliope is `local-only`, there is **no cloud fail-over** (R13). Async tasks **stay queued** (defer) until the local model is back; the interactive REPL surfaces the error to Lars (a live session can't defer). Drafting never silently substitutes a cloud model.
- **`mycelium_prod` unreachable** — `seed` and (future) passive learning **defer**; **drafting still works** from the existing `voice_style_guide` (graceful degradation — the learned artifact is local, not dependent on Mycelium at draft time).
- **Bad curation** — style-guide blocks are **versioned with changelogs**; `calliope rollback` restores a prior version. The curator must emit a changelog; an empty/degenerate rewrite is rejected and the prior version kept.
- **Cold start / empty corpus** — `voice_style_guide` begins from a minimal neutral template; drafts are generic until learning accrues. `calliope status` flags "unseeded."
- **Ambiguous brief** — the drafter is instructed (persona) to surface a clarifying question in the result rather than invent facts.

## 9. Test plan (TDD — failing test first, per repo protocol)

| # | Acceptance criterion (observable) |
|---|---|
| **S1** | `calliope seed` on a fixture corpus produces a non-empty, sectioned `voice_style_guide` v1 with **EN and DE** sections; `status` shows version + per-language source counts. |
| **W1** | `calliope chat` drafts in-session for an EN brief; the draft applies a style-guide rule (observable in output). |
| **T1 (bilingual)** | Given a German brief, the draft is in German; `/translate en` renders it in English preserving voice (style-guide EN rules applied — not a literal MT). |
| **L1** | An accepted session (steering + hand-edit) appends exactly one `EditRecord` carrying both `diff` and `steering[]` to `edit_log`. |
| **L2 (R9 core)** | Across **3 sessions** for a recurring intent, apply a *consistent* correction each time (steer "drop the hedging"). After curation, assert (a) `voice_style_guide` gained a matching rule, and (b) session 3 needs **fewer corrections** than session 1 (measurable drop). |
| **O1** | With the dispatcher stopped, a delegated `draft` task sits in `iris.tasks.calliope` (NATS-verifiable); on restart it drains and returns — nothing lost. |
| **H1 (hermeticity)** | A **dispatched** `draft` task's ephemeral container produces the **same draft** for a fixed brief + pinned style guide whether or not the host's global `~/.claude` config exists (per §7.6). |
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
| **CLI file-edit front door** | Non-interactive batch drafting: `write` → file → edit → `learn`. Deferred in favor of the chat REPL (now); useful later for scripted/bulk drafting. |
| **Cross-machine** | Mailbox truly on outpost; Calliope's worker on the laptop — makes offline/durability *fully* real (prototype Demos B/C). |
| **Per-register / per-recipient voice profiles** | Separate style guides for formal email vs. casual chat vs. specific recipients. |

## 12. Open spikes (resolve during build)

- **`mycelium_prod` schema** — introspect the read models: which tables/views hold Lars's **sent** emails and messages, how "sent by Lars" is identified, and how text/recipient/timestamp are exposed. Time-boxed before the corpus reader.
- **A2A ⇄ Letta bridge** — same spike as prototype §12; confirm the clean way to expose `calliope` as an A2A agent. **Partially resolved (M0.3):** Letta (v0.16.8, SDK `letta-client` 1.12.1) is used as the **memory plane only** — it stores the `calliope` agent + `persona`/`voice_style_guide` blocks (`agents.blocks.update/retrieve`) and auto-discovers the Ollama models (`ollama/gemma4:31b-mlx`). **Draft/translate generation runs via direct Ollama** (`/api/chat`, `think:false` — Gemma 4 is a thinking model and otherwise leaves `content` empty), not Letta's agentic tool-calling loop, since a local model is not a reliable tool-caller. This keeps the chat path robust and testable while Letta owns durable identity/memory (R8).
- **Curation cadence & guardrails** — tune the edit threshold and the "reject degenerate rewrite" check so the style guide improves without thrashing (vision §12 memory-drift risk).
- **Model — pinned (resolved via research, 2026-06-23):** **Gemma 4 31B Dense** via Ollama (`gemma4:31b-it-q8_0`, ~34 GB, or the Metal-optimized `gemma4:31b-mlx` for speed), `num_ctx 65536`. Chosen for best-documented **German + English + translation** strength and #3-open human-preference standing (natural, non-"AI-ese" prose), native system role for style-guide adherence, Apache 2.0, fits 128 GB easily. **Lean alternative (same family, drop-in):** Gemma 4 26B-A4B MoE (`gemma4:26b-a4b-it-q8_0`, ~3.8 B active) if interactive speed matters. **Not adopted locally:** Qwen3-235B-A22B-2507 — best open creative writer (EQ-Bench v3 0.875) but only fits this 128 GB box at side-loaded IQ3, eroding the prose/German quality it'd be chosen for. **Risk to validate (M1/M3):** some reviews call Gemma 4 prose "correct but bland" — if voice feels flat, bring **exemplar/pgvector grounding** (§11) forward. *(Model names from live web research beyond the Jan-2026 cutoff; re-confirm exact Ollama tags at M0 build time.)*

## 13. Milestones (rough)

| Milestone | Deliverable | Est. |
|---|---|---|
| M0 | Localhost containers (Letta, Postgres, NATS) + native model server reachable from a container; Calliope image builds; agent card served | ~1 session |
| M1 | Corpus reader + `seed` → `voice_style_guide` v1 (**S1, H1**) | ~1 session |
| M2 | Chat REPL → Letta draft/translate in-session (**W1, T1**) + async task path & offline durability via mailbox+dispatcher (**O1**) | ~1–2 sessions |
| M3 | Learn path: diff capture + curator + versioning/rollback (**L1, L2**) — the R9 proof | ~1–2 sessions |
| M4 | Portability + hardening (**P1**), polish CLI (`status`, `rollback`) | ~0.5–1 session |
