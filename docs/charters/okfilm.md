# Charter — O.K. Film und Medienproduktion
**Owns.** Client briefs, scheduling, production and editing coordination, delivery checklists. Its own floor in Subreal Manager (Bina → O.K. Film Katı), one room per role, separate from the library.

## Roles (one bounded worker per workflow)
| Room | Role | Agent id | Workflow | Deliverable | Tools |
| --- | --- | --- | --- | --- | --- |
| 1 Product | Product Manager | `okfilm-product-manager` | `okfilm.product_brief` | `product-brief.md` | read, evidence, missing, write |
| 2 Design | UI/UX Designer | `okfilm-uix-designer` | `okfilm.uix_spec` | `uix-spec.md` | read, evidence, missing, write |
| 3 Project | Project Manager | `okfilm-worker` | `okfilm.production_plan` | `production-plan.md` | + date_math |
| 4 Data | Data Engineer | `okfilm-data-engineer` | `okfilm.data_plan` | `data-plan.md` | read, evidence, missing, write |
| 5 Edit Suite | Video and Photo Editor | `okfilm-editor` | `okfilm.edit_plan` | `edit-plan.md` | + date_math |
| 6 Legal | Lawyer | `okfilm-lawyer` | `okfilm.legal_review` | `legal-review.md` | + date_math |

**Limits by role.** The UI/UX Designer and the Editor read text only: no images, video or footage. The Lawyer role is an issue-spotting assistant, not a licensed lawyer; its artifact opens with "Hukuki tavsiye değildir" and it may not state what the law requires, cite statutes or draft binding clauses.

**Never (all roles).** Sends a message, prepares or sends an invoice, publishes, signs, or contacts a client. Those would be future `action` approvals with a named destination.

**Acceptance.** Facts trace to the brief by file:line; assumptions and proposals are labelled; the owner accepts the specific artifact version.

## "CA/PA 180+" — what it does and does not mean here
The owner asked for an office built by looking at example repos rated CA/PA 180+ in the earlier "AM Genie Scout 26" scan (17 repos at CA ≥ 180 on 2026-11-17).
- Those numbers are that scan's **unverified estimates of the repos**. They are shown next to reference repos, labelled as such.
- **No agent in this office has a rating.** Ratings need a named evaluation with a date (see the 30-task experiment in `docs/architecture.md`).
- Repos actually read (README only, 2026-11-19): `paperclipai/paperclip` (188/200), `pbakaus/impeccable` (179/200), `addyosmani/agent-skills` (177/200), `alirezarezvani/claude-skills` (171/200). What was taken: goal-linked tasks with review gates and an org chart of roles; narrow critique/audit passes; spec before work; a product/project skill breakdown. No code was copied.
- Listed as references but **not read**: `tt-a1i/archify`, `nexu-io/open-design`, `ruvnet/ruflo`, `opendatalab/MinerU`, `unclecode/crawl4ai`, `Graphify-Labs/graphify`, `harry0703/MoneyPrinterTurbo`.
- The scan had no 180+ repo for video/photo editing or legal work.

**Status.** See `docs/first-report.md` and the run records in the core for which roles have live runs. All inputs so far are the synthetic brief; no real client data has been used.
