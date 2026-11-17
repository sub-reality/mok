# Evidence register
As of 2026-11-17. Categories: **VERIFIED** (checked in this session), **USER-REPORTED**, **INFERRED**, **HYPOTHESIS**, **OPEN**.

## Verified in the session that built this repository
| # | Fact | How |
| --- | --- | --- |
| V1 | Execution environment is a Linux cloud container, not the owner's Windows workstation. | `uname`, session description |
| V2 | Python 3.13.18, Node 22.23.4, `claude` CLI on PATH, `claude-agent-sdk` 0.2.172, `jsonschema` 4.26.0 are installed there. | `which`, `pip list` |
| V3 | A headless agent call through the Agent SDK with model `claude-fable-5-2` succeeds in that environment; every assistant message reported `model='claude-fable-5-2'`. | 4 completed/failed live runs, run records in the store |
| V4 | The CLI prints `[claude-code:unrecognized_model] claude-fable-5-2` on those calls and still serves the model. | run output |
| V5 | One live workflow per office reached `awaiting_review` with an artifact: okfilm (40 tool calls, 18 evidence records), institute (27, 23), school (9, 5). | `offices show`, exported recording |
| V6 | The first okfilm run failed with `budget_exhausted` at the 30-tool-call cap (18 of them `date_math`); the cap was raised to 90 and the retry completed. | run records |
| V7 | 20 core tests, 32 browser checks and 7 manager↔core end-to-end checks pass. | `unittest`, `manager/tests/ui.test.js` |
| V8 | Repo `sub-reality/mok` contained only `README.md` before this work. | `git log`, file listing |
| V9 | Contents of the owner's artifacts: AM Genie Scout 26, Vertical Archaeology, Sub-Realism Part IX, Sous les pavés la plage, Collectio Radicum, Roadmap & Çalışma Düzeni Kış 2026–27, Satz-Trainer, WORKOUT. | read through the artifact and docs tools |

## User-reported (not checked)
Workstation hardware (Ryzen 9 9950X, 128 GB, 4 TB, a 32 GB GPU of unknown model), QNAP TS-233, Tailscale/Sunshine/Moonlight, Galaxy S25 Ultra and Watch 5 Pro; existence of earlier workflow prototypes; the personal schedules in the winter document; disc herniation; the B2 course and exam window; that an FM27 demo exists.

## Inferred
- I1 A single-owner SQLite store with one writer at a time is enough for v0.1 (no concurrency test beyond sequential runs was made).
- I2 The usage figures the SDK reports (`total_cost_usd`) are estimates of API-equivalent cost, not what the owner's plan is billed.
- I3 "Hermes" and "Rea" are coordinator and rhythm-keeper role names chosen by the owner.

## Hypotheses (to be tested, not results)
- H1 Recurring tasks produce enough value to justify orchestration and upkeep.
- H2 Useful context can be processed within the owner's privacy boundaries.
- H3 A single-owner local-first design is sufficient for the required devices.

## Open
- O1 Whether the same SDK path works on the Windows workstation with the owner's login.
- O2 GPU vendor/model/VRAM; no local inference decision is possible before that.
- O3 The owner's real editing/shooting job list and dates (requested; not yet received).
- O4 Next-cycle dates of the expired external deadlines (not looked up in this session).
- O5 Status and dates of *Waiting for the Past*, *Cahiers du cinéma des simulacres*, *This is a pipe* — no source files read.
- O6 S Pen pressure and palm rejection on real hardware; watch glance view.
- O7 Framework and store shortlist from official sources (URL, licence, maintenance) — not researched in this session; see `architecture.md`.
- O8 The three `claude.ai/project/…` links could not be read.
- O9 Evidence for the self-hypnosis, pomodoro-length and nap claims in the private routines module was not searched.
