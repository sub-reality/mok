# Decision log

| Date | Decision | Alternatives | Evidence / reason | Outcome |
| --- | --- | --- | --- | --- |
| 2026-11-17 | Two projects in one workspace (`core/`, `manager/`), coupled only by `contract/v0.1` | Separate repositories | Spec allows one workspace; independent entry points and tests matter more than repo count | Built; each has its own tests |
| 2026-11-17 | Minimal hybrid architecture, no orchestration framework | See `architecture.md` | Three workflows needed only a loop, tools and a state machine | 3 live workflows reached review |
| 2026-11-17 | SQLite as the single authoritative store, local disk only | JSON files; Postgres | One owner, one machine; never a shared file on the NAS | In use |
| 2026-11-17 | Agent tools are in-process SDK tools; all built-in tools disabled | Let the agent use Read/Write/Bash in a sandbox directory | Permissions must be enforced in the executor; receipts per call | Tested: 5 hostile calls denied and receipted |
| 2026-11-17 | Model mismatch fails the run | Record and continue | "No silent substitution" | Covered by a test with a simulated substitution; not observed live |
| 2026-11-17 | Tool budget raised 30 → 90, turns 14 → 40 | Keep 30 and ask the agent to be terse | First live okfilm run exhausted 30 calls doing legitimate date arithmetic and evidence records | Retry completed with 40 calls |
| 2026-11-17 | Acceptance is left to the owner; no artifact was accepted by the session that produced it | Accept to demonstrate the full path | Acceptance is the owner's authority; the path is covered by tests | 3 tasks wait in `awaiting_review` |
| 2026-11-17 | School: answers are checked deterministically; the agent only reviews the attempt log afterwards | Let the model run the dialogue | One prompt at a time and privacy are easier to guarantee in code | Live review run completed; learner answers excluded from the exported recording |
| 2026-11-17 | Manager shows a recording exported from real runs when no core is reachable | Hand-written demo data | Fixture must not misrepresent what happened | Recording has 3 tasks, 191 events |
| 2026-11-17 | Plan Day 1 = 2026-11-17; historical external deadlines are kept and marked expired | Move every old date to 17.11 | Owner asked for the reset; the specification says expired deadlines stay expired | Implemented in the manager |
| 2026-11-17 | Personal routines are an opt-in, per-item-confirmed module in the manager | Seed them into the calendar | Specification: optional and private | Off by default |
| 2026-11-17 | Watch view, local inference, Windows/NAS/Obsidian setup deferred | — | Not reachable or explicitly "later" | Open |
