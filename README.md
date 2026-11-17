# mok — Agentic AI Offices & Subreal Manager 2027

Two independent projects in one workspace, joined only by a versioned contract.

| Folder | What it is |
| --- | --- |
| `core/` | **Project A.** Python package `offices`: SQLite task/event store, executor with enforced permissions, provider adapter (`mock`, `claude`), CLI, local read/command API. |
| `contract/v0.1/` | JSON Schemas for commands, events and the snapshot read model; state transitions and rules; fixtures. |
| `manager/` | **Project B.** Subreal Manager — management interface and optional game. Static page, installable as a PWA. |
| `.claude/agents/` | `hermes` (coordinator), `rea` (private routines), and the three office worker definitions. |
| `docs/` | Master specification, evidence register, decision log, architecture comparison, office charters, security model, first report. |

## Core quick start
```bash
cd core
python3 -m offices packet okfilm samples/okfilm/demo-brief
python3 -m offices create okfilm okfilm.production_plan "Plan" --packet demo-brief --due 2026-12-04 --as-of 2026-11-17 --queue
python3 -m offices run <task_id> --provider claude      # real agent loop; or --provider mock
python3 -m offices show <task_id>
python3 -m offices artifact <artifact_id>
python3 -m offices review <task_id> accept --sha <sha256>   # the owner's decision
```
Requires Python 3.11+, `jsonschema`, and for live runs `claude-agent-sdk` with a working Claude Code login. Data lives in `./.offices` (override with `--data` or `OFFICES_DATA`). `--sim` uses an isolated rehearsal store that only accepts the mock provider.

## Manager quick start
```bash
python3 manager/build.py
python3 -m http.server 8080 --directory manager          # open http://localhost:8080
cd core && python3 -m offices serve --port 8787 --origin http://localhost:8080   # optional live link; prints a token
```
Without a core the manager shows the bundled recording (`manager/fixtures/recording.json`, exported from real runs with `offices export-fixture`) and keeps any command you compose in an outbox marked "gönderilmedi".

## Tests
```bash
cd core && python3 -m unittest discover -s tests
node manager/tests/ui.test.js
```
