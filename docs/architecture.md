# Architecture: three alternatives and the decision gate

```
        ┌────────────────────────── Project A: core (system of record) ──────────────────────────┐
 owner ─┤ CLI  python3 -m offices …                                                              │
        │   │                                                                                    │
        │   ├─ service.handle(command, auth)  ── contract v0.1 validation, idempotency, versions │
        │   ├─ SQLite store: tasks · runs · tool_receipts · artifacts · evidence · approvals ·   │
        │   │                transfers · events(cursor)                                          │
        │   └─ executor.run_task ── Toolbox (allow-list, source root, output dir, budgets)       │
        │                             └─ provider adapter:  mock │ claude (Agent SDK) │ (local)   │
        │ local API 127.0.0.1 (token): GET snapshot · GET events?since · GET artifact · POST cmd │
        └───────────────────────────────────────────┬────────────────────────────────────────────┘
                                 contract v0.1 only │ (snapshot + ordered events, commands)
        ┌───────────────────────────────────────────┴────────────────────────────────────────────┐
        │ Project B: Subreal Manager (static PWA) — recording | live | rehearsal(synthetic)      │
        │ owns: layout, agenda pages + ink, planning cards, private routines, XP display, outbox │
        └────────────────────────────────────────────────────────────────────────────────────────┘
```

| | 1. Minimal cloud-assisted | 2. Hybrid (chosen, minimal form) | 3. Primarily local |
| --- | --- | --- | --- |
| Shape | One agent runtime, office profiles as prompts, files exchanged by hand | Local store + executor + permissions; inference behind an adapter; one bounded worker per office | Local models and tools; cloud only by explicit approval |
| Reasoning quality | High (frontier model) | High (same model) | Unknown until the GPU and a local model are verified; likely lower for long sourced writing |
| Autonomy | Good inside one session; no durable state | Bounded and resumable: state is outside model prose | Same structure as 2 |
| Privacy | Sources leave the machine on every run | Sources leave only for the run that reads them; store, receipts and approvals stay local | Best |
| Reliability | Depends on chat/session state | Failures are recorded states; retry is explicit | Adds model-serving failures |
| Maintenance | Lowest | Low: ~1,000 lines of Python, two dependencies | Highest: drivers, model updates, eval of each model |
| Latency / cost | Network; plan usage | Same per run; measured per run in the store | No per-run fee; hardware and time |
| Practical value now | Cannot show review boundaries or audit | Demonstrated: three workflows reached human review | Not demonstrable without the workstation |

**Recommendation.** Alternative 2 in its minimal form, as built: plain Python, SQLite, the Claude Agent SDK as the first provider, no orchestration framework.

**Critiques.** *Architect:* the store and executor are in one process; a second writer (e.g. the API and a run at once) relies on SQLite locking only. *Security engineer:* path confinement and tool allow-lists are tested, but the worker process itself is not sandboxed at OS level; built-in tools are disabled by configuration (`tools=[]`, `strict_mcp_config`, `setting_sources=[]`), which is one layer, not two. *Researcher:* locators are checked for existence, not for whether the quoted words match the line. *End user:* everything real still needs a terminal; the manager cannot start a run.

**Strongest objection.** For a single owner, a well-kept folder plus ordinary Claude sessions (alternative 1) may deliver the same artifacts with no system to maintain.

**Experiment that could disprove the recommendation.** The 30-task comparison in the specification (10 per office, matched tasks, current workflow vs. this system). If median active human time is not at least 25% lower, or weekly upkeep exceeds 60 minutes over four weeks, or any unauthorized action occurs, stop expanding and fall back to alternative 1. Dataset, rubric, budget cap and rollback are to be written before it starts. It has not been run.

**Frameworks and stores.** Considered and not adopted at this stage: an orchestration framework (LangGraph, CrewAI, AutoGen, OpenAI Agents SDK) — nothing in v0.1 needs a graph runtime, and each adds upkeep; vector stores (Qdrant, Chroma, pgvector) — no retrieval need has been shown; packets are small and read whole. Local serving (Ollama, llama.cpp, vLLM) is blocked on GPU verification. No official-source review (URL, licence, maintenance evidence) of these was done in this session; that review is owed before any of them is added.
