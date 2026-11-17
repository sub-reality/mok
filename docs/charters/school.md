# Charter — Education: School
**Owns.** *My Learning* (German/English practice) and *My Teaching* (course design, GNR), kept separate.
**Workflow v0.1.** `school.lesson`: a bounded lesson from an approved deck, one prompt at a time. Checking is deterministic. *Socratic* mode gives laddered hints and never hands over the answer after a wrong attempt; *direct* mode shows the correction and is a separate, explicit mode. Attempts and hints are recorded. Afterwards the worker reads the attempt log and proposes the next retrieval task, raising one difficulty dimension.
**Worker tools.** list_sources, read_source, record_evidence, report_missing, write_artifact.
**Never.** Claims learning gains without a later assessment; exposes learner answers to presentation clients.
**Decks.** `fokus4-neue-arbeit.json` (six cards from the owner's Satz-Trainer, Fokus Deutsch B2 unit 4). A GNR verb-ladder deck for My Teaching is not written yet.
**Status.** One live review run reached review on 2026-11-17; the attempts in that session were typed by Claude as a test, not by a learner.
