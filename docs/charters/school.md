# Charter — Okul (School)
**Position.** A department **affiliated to the Enstitüt**, with its **own floor, its own department structure and its own permission boundary**. In the core it is the separate office `school`: Institute workers cannot read School decks or attempt logs, and School workers cannot read Institute or O.K. Film sources (tested).

## Two language departments
| Department | Side | Agent id | Workflow | Deliverable |
| --- | --- | --- | --- | --- |
| **Almanca Bölümü** | My Learning — the owner learns German (B2 course, telc DTB B2 target as stated in his Satz-Trainer) | `school-worker` | `school.lesson` | `next-retrieval.md` |
| **İngilizce Bölümü** | My Teaching — the owner teaches English with his GNR method | `school-english-planner` | `school.lesson_plan` | `lesson-plan.md` |

**Almanca — `school.lesson`.** A bounded lesson from an approved deck, one prompt at a time. Checking is deterministic. *Socratic* mode gives laddered hints and never hands over the answer after a wrong attempt; *direct* mode shows the correction and is a separate mode. Attempts and hints are recorded; afterwards the worker reads the log and proposes the next retrieval task, raising one difficulty dimension. Deck: `fokus4-neue-arbeit.json` (six cards from the owner's Satz-Trainer, Fokus Deutsch B2 unit 4).

**İngilizce — `school.lesson_plan`.** From approved course notes, one GNR lesson plan: target verb, the single dimension raised, a 6–8 rung sentence ladder with two Socratic hints per rung, natural repetition, a separate direct-correction drill, a self-correction and transfer check.

**Never.** Claims learning gains without a later assessment; exposes learner answers or individual learner records to presentation clients; sends anything to learners.

**Status.** German: one live review run (attempts typed by Claude as a test, not by a learner). English: see run records; the only input so far is a synthetic course note. No real learner data has been used. A real GNR deck and the owner's own course material are not in the system yet.
