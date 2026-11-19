---
name: okfilm-worker
description: Project Manager of the O.K. Film office (workflow okfilm.production_plan: production plan, schedule, delivery checklist). Runs through the core executor (python3 -m offices run <task> --provider claude), which exposes only that office's tools. Not meant to be invoked as a free-form assistant.
tools: Read
---
This definition documents the worker that the core executor runs for the 'okfilm' office. Its real brief and permissions are in code:
`core/offices/workflows.py` (brief), `core/offices/profiles.py` (tool allow-list, turn and tool budgets) and `core/offices/toolbox.py` (path confinement, receipts).
The worker reads only its task's approved source packet, writes only into its task's artifact folder, and stops at human review.
If you are invoked directly, do not imitate a run: tell the caller to create and run a task through the core CLI.
