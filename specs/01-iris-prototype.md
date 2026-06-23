# Iris Prototype — Spec

**Version:** 0.1
**Date:** 2026-06-09
**Status:** Draft for review
**Depends on:** `00-iris-vision-and-stack.md`
**Implements:** R1–R8 (partial), proves §7.1 (tier delegation) and §7.3 (offline durability)

---

## 1. Objective

Prove the **two hero behaviors** end-to-end with the thinnest possible slice — enough to validate the architecture's two riskiest claims, nothing more:

- **Demo A — Tier escalation:** a small local-model agent recognizes a coding task exceeds its tier and delegates to a frontier coding agent, then integrates the result.
- **Demo B — Offline durability:** a task delegated to an offline laptop agent is picked up when the laptop reconnects.
- **Demo C — Combination:** the escalation target (laptop coding agent) is offline → the task queues → resumes and completes on reconnect.

If these three pass, the two things the research said are unsolved/hard (model-tier delegation, offline durability) are demonstrably solved in *our* composition. Everything else in the vision is then incremental.

## 2. Success criteria (acceptance)

| # | Observable outcome |
|---|---|
| **A1** | Send a trivial task ("summarize this string") to the small agent → it answers locally, **no delegation** occurs (log shows `route=local`). |
| **A2** | Send a coding task ("write a Python function that …") to the small agent → router/agent classifies it above tier → **A2A-delegates** to the coding agent → small agent returns the coding agent's result. Log shows `route=delegate tier:small-embedded→frontier-coding`. |
| **B1** | With the laptop worker **stopped**, delegate a task to the laptop agent → caller gets `accepted/working` immediately; task sits in `iris.tasks.laptop` (verifiable via NATS). |
| **B2** | **Start** the laptop worker → task is drained and executed within seconds → result is posted back and retrievable by the original task id. **Nothing lost.** |
| **C1** | Coding agent runs **on the laptop** (local code model) and is **offline** at delegation time → task queues (B-path) → on reconnect, executes and the small agent integrates the result. |
| **D1** *(stretch)* | After running the same recurring task 3×, the small agent's Letta memory shows a curated note that shortcuts the 3rd run (self-learning smoke test). |

A demo is "passing" only with a **logged trace** and an **automated test** (§9) — not a manual eyeball.

## 3. Scope

**In scope:** 3 agents, 2 hosts, A2A delegation, tier decision, NATS mailbox + pull-worker, Letta-backed state, one MCP tool (filesystem) for the coding demo, a thin LangGraph router.

**Out of scope (deferred to P1+):** signed Agent Cards / auth, scope attenuation, Temporal, fail-over/circuit-breaker (Demo C uses plain defer, not fail-over), multi-tier ladders beyond 2 tiers, Mycelium read-model tools, dashboard/UI, multi-user, the self-learning loop beyond the D1 smoke test.

## 4. Topology

| Role | Host | Notes |
|---|---|---|
| Control plane | **outpost** | Letta server, Postgres, NATS JetStream, LangGraph router, A2A endpoints + mailboxes |
| Frontier coding agent | **cloud** (API model) for Demo A; **laptop** (local code model) for Demo C | Same agent, two model bindings — proves model-portability |
| Small local agent | **laptop** | Local small model (3B–8B), runs as a NATS pull-worker |

> **Dev shortcut:** for first bring-up, collapse "outpost" onto the laptop (everything localhost), then split outpost↔laptop onto two hosts to prove the cross-machine + offline legs. The split is what makes B/C real.

## 5. Components & versions (pinned)

| Component | Version / source | Role in prototype |
|---|---|---|
| Letta | v0.16.8 (self-host server + Python SDK) | Agent identity, memory, model binding |
| LangGraph | current stable + checkpointer (Postgres) | Router graph; `interrupt()`/resume for Demo C |
| A2A | Python SDK, spec v1.0.x | Agent Cards + delegation transport |
| NATS + JetStream | current stable (single binary on outpost) | `iris.tasks.<node>` durable streams; pull-worker |
| MCP | filesystem server | Coding agent's file read/write tool |
| PostgreSQL | one instance (port per Mycelium convention) | Letta state + LangGraph checkpoints |
| Language | **Python 3.12** | All SDKs first-class in Python; A2A keeps it interoperable with Elixir later |

## 6. Data model

**6.1 Agent Card tier extension** (served at each agent's `/.well-known/agent-card.json`):
```json
{
  "name": "small-local",
  "url": "https://outpost/iris/agents/small-local",   // mailbox, not laptop IP
  "skills": [{"id": "chat"}, {"id": "summarize"}],
  "x-iris": {
    "model": "qwen3-4b-instruct",
    "tier": "small-embedded",            // ordered ladder, see registry
    "max_task_class": "simple",
    "node": "laptop"
  }
}
```

**6.2 Tier ladder** (prototype = 2 rungs): `small-embedded(0) < frontier-coding(10)`.

**6.3 Task envelope** (published to NATS / passed over A2A):
```json
{
  "task_id": "uuid",
  "from": "small-local",
  "to": "code-agent",
  "skill": "code",
  "required_class": "coding",
  "payload": {"prompt": "...", "context": "..."},
  "reply_subject": "iris.results.<task_id>",
  "created_at": "<stamped by caller>"
}
```

**6.4 NATS subjects:** `iris.tasks.<node>` (durable, work-queue retention), `iris.results.<task_id>` (reply), `iris.presence.<node>` (heartbeat).

**6.5 Tier registry** (outpost, in Postgres or a JSON file for P0): `agent → {tier, node, a2a_url, last_heartbeat}`, built from Agent Cards + presence.

## 7. Flows

**Flow A — escalation (online):**
1. Caller → small agent (A2A) with a coding task.
2. Router graph `assess` node classifies `required_class=coding`.
3. small-embedded(0) < coding requirement → `route=delegate`; registry resolves `code-agent` (cloud, tier 10).
4. A2A call → code-agent (uses MCP filesystem tool, writes/returns code).
5. small agent returns the result to caller; logs the trace.

**Flow B — offline durability:**
1. Caller → laptop agent's **mailbox** (outpost) with a task.
2. Mailbox publishes envelope to `iris.tasks.laptop`, returns `working` + `task_id`.
3. Laptop offline → message waits in JetStream.
4. Laptop worker reconnects → pull-consumes → executes on local model → publishes to `iris.results.<task_id>`.
5. Caller (subscribed / polling the result subject) receives it. Assert nothing lost.

**Flow C — combined (escalation target offline):**
1. Flow A, but `code-agent` is bound to the **laptop** local code model and is offline.
2. Router's delegate edge sees target offline (no recent presence) → takes the **defer** path → publishes to `iris.tasks.laptop` and the router graph `interrupt()`s, checkpointed.
3. Laptop reconnects → worker drains → code-agent runs → result to `iris.results.<task_id>`.
4. A small resumer service consumes the result → resumes the checkpointed router graph → small agent integrates and returns.

## 8. Implementation tasks (TDD — write the failing test first)

> Follow the bug-fix/feature protocol: red → green, and for each acceptance criterion keep the test that proves it.

- **M0 — Infra (outpost/local):** Postgres up; NATS+JetStream up with streams `iris.tasks.*`, `iris.results.*`; Letta server running. *Test:* health-check script asserts all three reachable.
- **M1 — Agents + cards:** define 3 Letta agents (small-local, code-agent, + a caller harness); serve Agent Cards with `x-iris` tier ext; build the tier registry from cards + presence. *Test:* registry resolves each agent's tier/url; `assert tier(small-local) < tier(code-agent)`.
- **M2 — Router + tier decision (A1/A2 logic):** LangGraph router graph with `assess` + conditional edge (`local | delegate | defer`); a cheap task classifier. *Test:* trivial task → `route=local`; coding task → `route=delegate` (target online).
- **M3 — A2A online delegation (Demo A):** wire the `delegate` edge to an A2A client call; code-agent exposes A2A server + MCP filesystem tool. *Test = A1, A2* with logged trace.
- **M4 — Mailbox + NATS pull-worker (Demo B):** mailbox endpoint publishes to `iris.tasks.<node>` and returns `working`; laptop worker is a durable pull consumer that executes + replies. *Test = B1* (worker stopped → queued), *B2* (worker started → drained, result returned, nothing lost).
- **M5 — Combined + resume (Demo C):** presence heartbeat; router `defer` path → `interrupt()` + checkpoint; resumer service resumes graph on result. *Test = C1* (target offline → queue → reconnect → integrated result).
- **M6 — Self-learning smoke (D1, stretch):** run a recurring task 3×; assert a curated Letta memory block exists and the 3rd run references it. *Test = D1.*

## 9. Test plan

- **Unit:** classifier (task → required_class), registry tier comparison, envelope (de)serialization.
- **Integration (the acceptance table):** A1, A2, B1, B2, C1 as automated tests driving real Letta/A2A/NATS (testcontainers or a local compose). Each asserts the **logged route trace** + the **observable result**.
- **Chaos (manual, then scripted):** kill the laptop worker mid-flight (B/C); assert resume. Swap code-agent's model cloud↔local (proves model-portability) — memory/identity unchanged.
- **Regression guard (per bug protocol):** for any bug found, add a failing test, fix, confirm, revert-to-verify-catch, re-apply.

## 10. Milestones & rough effort

| Milestone | Deliverable | Est. |
|---|---|---|
| M0–M1 | Infra + agents + registry, all-localhost | ~1 session |
| M2–M3 | **Demo A passing** (tier escalation, online) | ~1–2 sessions |
| M4 | **Demo B passing** (offline durability) | ~1–2 sessions |
| M5 | **Demo C passing** (combined, split hosts) | ~1–2 sessions |
| M6 | Self-learning smoke (stretch) | ~0.5 session |

## 11. Explicitly deferred (do NOT build in P0)

Signed cards / auth · scope attenuation · Temporal · fail-over & circuit-breaker (C uses plain defer) · >2 tiers · Mycelium tools · dashboard · the full self-learning loop · multi-user. These are P1+ in the vision roadmap.

## 12. Open spikes (resolve during P0, feed back into vision §12)

- **A2A ⇄ Letta bridge:** confirm the cleanest way to expose a Letta agent over A2A (Letta's native multi-agent messaging is its own layer). Time-boxed spike before M3.
- **Classifier:** rules vs. a tiny model call for `required_class`. Start with rules; measure misroutes.
- **Resume ergonomics:** LangGraph `interrupt()` + external-result resume — validate it's not fragile before declaring Temporal unnecessary for P1.
