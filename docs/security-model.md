# Security model (v0.1)

**Assets.** Client briefs, research corpus, learner records, the task/approval record, credentials for the model runtime.

**Trust boundaries.**
1. *Owner ↔ core.* The CLI on the owner's machine is the owner. The local API binds `127.0.0.1`, requires a bearer token printed once at start, and allows one browser origin.
2. *Core ↔ agent.* The agent is not trusted. It gets only the tools in its office's allow-list. Every call passes `Toolbox.call`, which checks the allow-list, confines reads to the task's source packet and writes to the task's artifact folder (plain file names only, fixed extensions, size caps), counts against a budget, and writes a receipt.
3. *Core ↔ sources.* Source files, and anything an agent reads, are data. The worker brief says so; the real protection is that no tool can send, publish, pay or reach the network.
4. *Core ↔ manager.* The manager receives the redacted snapshot, events with minimal payloads, and artifact bodies only on request. It can submit commands; it cannot start runs or touch the database. Authority comes from the transport's authentication; `actor` and `scope` in the command body are checked claims.

**Approvals.** A decision carries the sha256 of the artifact that was reviewed and the task version. If the file on disk or the latest recorded artifact differs, the decision is rejected (`approval_stale`). Agents cannot issue `approval.decide`.

**Rehearsal.** A store is created either live or as rehearsal and cannot be reopened as the other. A rehearsal store refuses any provider except `mock`; all its events carry `simulation: true`.

**Secrets.** None are stored by this code. The Claude runtime uses the machine's own Claude Code login. The API token lives in memory only; the manager keeps it for the page session only.

**Known gaps.**
- No OS-level sandbox around the agent process; disabling built-in tools is by SDK configuration.
- Evidence locators are checked for existence, not for a match between the note and the line.
- No encryption at rest, no backup or restore test yet.
- The local API has no rate limit and no TLS (loopback only).
- Learner answers are stored in clear text in the local store.
- The exported recording contains artifact bodies for the okfilm and institute offices; export before sharing should be reviewed by the owner.
