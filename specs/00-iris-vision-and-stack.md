# Iris — Distributed Self-Learning Agent Mesh

**Codename:** Iris *(working name — Greek messenger goddess, beside Hermes; placeholder, rename freely)*
**Version:** 0.1
**Date:** 2026-06-09
**Status:** Draft for review
**Author:** Lars + Claude

---

## 1. Vision

A mesh of **stateful, self-learning agents** that run wherever it makes sense — laptop, outpost, cloud — and behave as one system:

- They **discover and talk to each other natively**, across machines and vendors, without sharing internal state.
- Each agent **knows what model it is running on** and adjusts what it attempts to its capability tier.
- An agent that hits the edge of its competence **delegates to a more capable peer** — e.g. a small local agent hands a coding task to a frontier coding agent.
- Agents **survive going offline**: work addressed to a sleeping node waits and is picked up on reconnect.
- **Memory and identity persist independent of compute and model** — an agent keeps what it knows even as its host or underlying LLM changes.
- Agents **learn from their own lived experience** by curating their memory over time (the pattern Lars likes from the Hermes agents).

The thesis: *availability, intelligence, and memory are three separate concerns.* Iris keeps them separate so a part-time laptop, an always-on outpost, and an elastic cloud can compose into one coherent, durable agent fabric.

## 2. North-star scenarios

The system is "done enough" when these all work:

1. **Tier escalation** — A small local-model agent recognizes a task exceeds its tier and delegates to a frontier coding agent, then integrates the result.
2. **Offline durability** — A task delegated to an offline laptop agent is picked up the next time the laptop opens; nothing is lost.
3. **Always-on resilience** — An outpost agent whose preferred model lives on the laptop keeps functioning (fail over to an always-on model, or defer the model-bound part) while the laptop is dark.
4. **Self-learning** — Agents refine their own memory from past sessions and visibly improve at recurring tasks.
5. **Cross-substrate identity** — An agent keeps its memory and personality when its underlying model is swapped or its host moves.

## 3. Goals / Non-goals

**Goals**
- Run the same agent abstraction on laptop, outpost, and cloud.
- Native, standards-based agent-to-agent communication (no bespoke RPC).
- First-class, **explicit model-tier awareness and capability-based delegation** (the requirement nothing ships out of the box — see §7.1).
- Durability across intermittent connectivity and intermittent model availability.
- Persistent, self-editing memory decoupled from the model.

**Non-goals**
- Not building a new LLM, a new agent protocol, or weight-level fine-tuning.
- Not a general-purpose workflow/BPM platform.
- Not (initially) a multi-tenant or multi-user product — single operator (Lars).
- Not replacing Mycelium/Lighthouse — Iris is the **agent-consumer layer** that reads from them.

## 4. Glossary

| Term | Meaning |
|---|---|
| **Node / Host** | A machine that can run agents: `laptop` (u26, intermittent), `outpost` (always-on Linux), `cloud` (API endpoints / managed runtimes). |
| **Agent** | A stateful Letta agent: identity + persistent memory + a configured model + tools. |
| **Model tier** | A declared capability class for the agent's current model, e.g. `frontier-coding`, `general`, `small-embedded`. |
| **Agent Card** | A2A capability descriptor (JSON at `/.well-known/agent-card.json`) — extended here with tier metadata. |
| **Mailbox** | An always-on endpoint that *is* an agent's addressable identity; holds inbound tasks while the agent's executor is offline. |
| **Delegation** | One agent handing a task to another agent over A2A. |
| **Escalation** | Delegation specifically *up* the tier ladder, because a task exceeds the sender's competence. |
| **Worker** | A process that pulls tasks from the durable queue and executes them (the laptop runs one). |
| **Control plane** | The always-on services on outpost: state, orchestration, transport endpoints, queue. |

## 5. Requirements (traceable)

**Functional**
- **R1** Agents run on laptop, outpost, and cloud under one abstraction.
- **R2** Agents discover and message each other over a standard protocol without sharing internal state.
- **R3** Each agent declares its model tier; peers can read it before delegating.
- **R4** An agent can detect a task is beyond its tier and escalate to a higher-tier agent.
- **R5** A task delegated to an offline node is durably held and executed on reconnect.
- **R6** An in-flight multi-step task resumes from its last completed step after an outage (no full restart).
- **R7** An always-on agent stays functional when its preferred (intermittent) model is unreachable — via fail-over or deferral.
- **R8** Agent state, memory, and identity persist independent of model and host.
- **R9** Agents curate/refine their own memory across sessions (self-learning).

**Non-functional**
- **R10** Always-on control plane fits a few GB RAM on outpost (see §9).
- **R11** Language-agnostic boundaries — Python agents and Elixir (Mycelium) interoperate over A2A/queue.
- **R12** Agent identity is verifiable; delegated authority can only narrow, never widen (§10).
- **R13** Local-only data (privacy-sensitive inference) never leaves the laptop unless explicitly allowed.

## 6. Architecture

Six planes, each owned by one component so responsibilities don't overlap:

| Plane | Owner | Responsibility |
|---|---|---|
| Identity & State | **Letta** | What an agent *is* and *knows*; persists across restarts/model swaps |
| Orchestration | **LangGraph** | *How* a task is reasoned through; the tier-routing / escalation decision |
| Transport | **A2A** | Agent-to-agent calls across machines/vendors |
| Durability | **NATS JetStream** *(Temporal optional, §8)* | Holding work for offline nodes; resume |
| Execution | **Local/cloud models + workers** | Actually running inference |
| Tools | **MCP** | What an agent can *do* (files, data, Mycelium read models) |

```
                                   ┌─────────────────── CLOUD ───────────────────┐
                                   │  Frontier coding agent (API model)           │
                                   │  exposed as A2A agent (tier: frontier-coding) │
                                   └───────────────▲──────────────────────────────┘
                                                   │ A2A (JSON-RPC/gRPC/HTTPS)
                                                   │
┌──────────────────────────── OUTPOST (always-on control plane) ────────────────────────────┐
│                                                                                            │
│   Letta server ── Postgres (agent state, memory, pgvector)   ← shared by LangGraph/queue   │
│        │                                                                                   │
│   LangGraph orchestrator  ──►  Router/Supervisor graph (tier decision, escalation)         │
│        │                         • run locally  • A2A-delegate  • enqueue for offline node │
│   A2A endpoints (Agent Cards, incl. mailboxes for intermittent agents)                     │
│   NATS JetStream (durable task streams, per-node subjects)                                 │
│   MCP servers (filesystem, Mycelium read models, …)                                        │
│   Always-on base model (small/mid, local) + cloud-API fallback                             │
└───────────────▲───────────────────────────────────────────────────────────▲──────────────┘
                │ A2A / NATS (online legs)                                    │
                │                                                             │ reads (RO Postgres)
        ┌───────┴──────── LAPTOP (u26, intermittent worker) ────────┐   ┌────┴───────────────┐
        │  NATS pull-worker  ──drains──►  laptop agent(s)            │   │ Mycelium / Lighthouse│
        │  Local models: 3B…70B (tier: small-embedded … local-fron) │   │ (data + intelligence)│
        │  A2A endpoint (online only); mailbox lives on outpost      │   └─────────────────────┘
        └────────────────────────────────────────────────────────────┘
```

**Topology principle:** *availability lives on outpost, intelligence can live anywhere, the laptop is an optional accelerator.* An agent's **addressable identity (mailbox) is always on outpost**; its **execution** may be intermittent (laptop) — see §7.2.

## 7. Key mechanisms

### 7.1 Model-tier-aware delegation — the part nothing ships

Research (2026-06-09) confirmed: **no mainstream runtime or protocol treats "which model am I, and should I delegate up" as a first-class primitive.** A2A Agent Cards carry no model/tier field and define no auto-escalation; Letta gives model-*portability* but not tier self-assessment; Microsoft Agent Framework's Handoff is author-declared, not competence-driven. True tier-aware routing exists only in research (OI-MAS, arXiv:2601.04861). **So Iris builds this itself**, thinly, on top of the standards:

- **Tier declaration** — every Agent Card carries an `x-iris` extension: `{ model, tier, skills[], max_task_class }`. Tiers are an ordered ladder, e.g. `small-embedded < general < frontier-general < frontier-coding`.
- **Tier registry** — outpost keeps a map of live agents → tier → A2A endpoint (built from Agent Cards + a presence heartbeat).
- **The router** — a LangGraph supervisor graph (on outpost) is the entrypoint for any task. It:
  1. **assesses** the task's required class (cheap classifier or rules),
  2. compares to the handling agent's tier,
  3. routes on a conditional edge:

```
            ┌─ within tier ──────────────► execute locally (tools / MCP)
 assess ───►├─ above tier, specialist online ─► A2A call (delegate up)
            └─ above tier, specialist offline ─► enqueue on node's stream (defer, §7.3)
```

- **Delegate tool** — low-tier agents also get a `delegate(skill, payload)` tool so escalation can be *agent-initiated* ("I can't do this, ask the coding agent"), not only router-initiated. Routes via the registry → A2A.
- **Honest scope:** this is orchestrator-layer logic, not magic. OI-MAS is the design reference, not a dependency.

### 7.2 Identity / execution split (the mailbox)

To make an intermittent agent look always-available:

- The agent's **Agent Card points at a mailbox endpoint on outpost**, not at the laptop's IP.
- The mailbox **accepts** a delegated task, persists it to the node's durable stream, and returns `working` immediately.
- The real agent's **worker on the laptop pulls** the task when the laptop is online, executes (on the local model), posts the result back.
- To any delegator, the laptop agent is a normal, reachable A2A agent — latency just varies.

### 7.3 Offline durability (pull, don't push)

A2A is request/response — pushing to an offline node fails. So **invert it: nodes pull.**

- Each node has a **durable NATS JetStream subject** (`iris.tasks.<node>`).
- Delegation to a node = publish to its subject (via the mailbox). Offline → the message waits per retention (days).
- The node's worker is a **durable pull consumer**; on reconnect it drains pending tasks.
- Multi-step tasks (**R6**) resume from the last completed step via the **LangGraph checkpointer** (Postgres-backed) — the graph hits an `interrupt()` awaiting the node's result and resumes when the result message arrives.

### 7.4 Availability rule (R7)

**An always-on agent must never bind its *primary* model to an intermittent host.** Concretely:

- Outpost agents run on an **always-on base model** (local small/mid model on outpost, or a cloud API) with a declared **fallback chain**.
- The laptop's model is exposed as a **delegated capability** (a worker on `iris.tasks.laptop`), never as anyone's base model.
- Per-task decision when a model-bound call can't reach the laptop:
  - task **allows substitution** → **fail over** to an always-on model (Letta model-swap, keep memory),
  - task **requires** the laptop model (privacy / local-only fine-tune) → **defer** to the queue.
- Resilience chain on synchronous attempts: **retry+backoff → circuit-breaker → fail-over | defer**, gated by a presence heartbeat so doomed calls aren't attempted.

### 7.5 Self-learning memory (R9)

- Letta provides persistent, self-editing memory; **memory subagents** periodically review sessions and rewrite/refine context.
- **Honest caveat (carry into expectations):** this is *learning in token space* — in-context memory curation, **not weight-level learning**. If the model never chooses to save something, it's gone. Iris treats memory quality as a thing to *engineer* (review cadence, what to persist), not a free lunch.

## 8. Component stack

| Layer | Pick | Version (as of 2026-06-09) | Why |
|---|---|---|---|
| Self-learning runtime / state | **Letta** (ex-MemGPT) | v0.16.8 (2026-05-14) | Stateful agents, persistent self-editing memory, model-portability, local CLI + cloud API |
| Orchestration / routing | **LangGraph** | current stable; A2A via `langgraph-api ≥ 0.4.21` (Agent Server) | Conditional-edge graphs = home for the tier router; durable checkpointer for R6 |
| Agent-to-agent transport | **A2A Protocol** | spec v1.0.0 (2026-03-12), release v1.0.1 (2026-05-28), Linux Foundation | Cross-machine/vendor agent comms; Agent Cards; in all 3 clouds |
| Tools / data | **MCP** | AAIF founding project; 10k+ servers | Tools + Mycelium read-model access |
| Durability / queue | **NATS JetStream** *(default)* | current stable | Durable per-node streams; offline pickup at ~100 MB |
| Durability *(optional, on growth)* | **Temporal** | — | Promote when multi-step cross-machine workflows multiply (see §8.1) |
| State store | **PostgreSQL** (shared) | — | One instance: Letta memory + LangGraph checkpoints (+ Temporal if adopted) |

### 8.1 Temporal: optional, not key (decision recorded)

Every durability requirement (R5–R7) is met by **NATS JetStream + LangGraph checkpointer + app-level retry** at ~100 MB. **Promote Temporal to a core element when**: cross-machine multi-step workflows proliferate and hand-rolled "resume-graph-on-result" glue turns fragile; or you need first-class durable timers/signals/sagas + deterministic replay + operational visibility; or reliability stakes outgrow homelab. Migration is **non-throwaway** — wrap existing LangGraph graphs as Temporal activities (Temporal outside, LangGraph inside). Default: ship on NATS, adopt at the complexity inflection.

## 9. Resource budget (RAM)

Framework overhead is small and predictable; **the model dominates.**

| Component (outpost) | RAM | | Model (laptop, Q4) | RAM |
|---|---|---|---|---|
| Letta server | 0.5–1 GB | | 3B small-embedded | ~2–3 GB |
| Postgres (shared) | 0.5–1 GB | | 7–8B | ~5–6 GB |
| LangGraph + A2A endpoints | 0.3–0.7 GB | | 30B-class | ~18–22 GB |
| MCP servers (few) | 0.2–0.5 GB | | 70B | ~40 GB |
| **NATS JetStream** | **~0.05–0.15 GB** | | **Cloud-API frontier** | **~0 local** |
| *(Temporal alt: +1.5–2.5 GB, +~2 GB if ES)* | | | | |

**Always-on control plane (NATS): ~2–3.5 GB** on outpost. With Temporal+ES: ~5–7 GB. On the 128 GB laptop the frameworks are noise — budget for the model. Biggest single lever: **NATS over Temporal**.

## 10. Security & identity

- **Verifiable identity (R12)** — A2A v1.0 **Signed Agent Cards** for cryptographic identity; presence heartbeats authenticated.
- **Scope attenuation** — delegated authority (tools/budget/domains/time) may only **narrow**, never widen, down a delegation chain (AIP pattern; note: this is the *opposite* direction from tier escalation — escalation routes *work up*, authority only flows *down*).
- **Local-data boundary (R13)** — tasks tagged `local-only` are never substituted to a cloud model; they defer to the laptop instead (§7.4).
- **Secrets** — model/API keys per node; laptop never holds cloud-frontier keys it doesn't need.

## 11. Relationship to existing systems

- **Mycelium** — Iris agents are **read-only consumers** of Mycelium's read models (via MCP server over the existing `readonly` Postgres role). Iris does not write into Mycelium's event log except as an explicit, designed consumer event.
- **Hermes agents (atlas, kubera)** — candidate **first citizens**: wrap each as an Iris agent (mailbox + Agent Card + tier) so the existing morning-brief / business-domain agents gain cross-node delegation and durability.
- **Outpost** — the control-plane host (already runs Mycelium prod + hermes in podman). Iris services deploy alongside, sharing Postgres where sensible.

## 12. Risks & open questions

- **Tier classification quality** — misjudging a task's required class causes needless escalation or local failure. Needs a cheap, tunable classifier + feedback. *(Validate in prototype.)*
- **Memory drift** — self-editing memory can degrade; needs review cadence + guardrails. *(R9 is engineered, not free.)*
- **A2A ⇄ Letta integration shape** — Letta's native multi-agent messaging is its own layer, not A2A; the A2A bridge is integration work, not built-in. *(Spike in prototype.)*
- **Governance split** — A2A and MCP sit under separate Linux Foundation umbrellas; watch for convergence.
- **Elixir interop** — Mycelium is Elixir; Iris agents are Python. Boundaries are A2A/NATS (language-agnostic) — confirm the NATS/A2A bridge ergonomics.
- **Open:** memory-layer choice (Letta in-context vs Zep/Graphiti/Mem0 graph-temporal) — not yet benchmarked for this workload.

## 13. Roadmap

| Phase | Outcome |
|---|---|
| **P0 — Prototype** | Two hero behaviors end-to-end (see `01-iris-prototype.md`): tier escalation + offline durability, 3 agents, 2 hosts. |
| **P1 — Mailboxes & registry** | Stable mailbox pattern, tier registry, presence heartbeats; wrap one real hermes agent. |
| **P2 — Resilience** | Fail-over/defer (R7), circuit-breaker, multi-step resume (R6) under real outages. |
| **P3 — Memory** | Self-learning loop tuned; memory-layer bake-off; measurable improvement on a recurring task. |
| **P4 — Fleet** | Multiple agents across all three substrates; Mycelium read-model tools; security hardening (signed cards, scope). |
| **P5 — Scale decision** | Re-evaluate Temporal at the workflow-complexity inflection (§8.1). |
