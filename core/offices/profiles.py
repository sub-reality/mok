"""Office profiles: an office is a permission and workflow boundary, not a set of always-on processes."""
from __future__ import annotations
from dataclasses import dataclass, field

READ_TOOLS = ["list_sources", "read_source"]
WRITE_TOOLS = ["write_artifact", "record_evidence", "report_missing"]
DATE_TOOLS = ["date_math"]

@dataclass(frozen=True)
class AgentDef:
    id: str
    office: str
    role: str
    tools: tuple[str, ...]
    max_turns: int = 40
    max_tool_calls: int = 90

@dataclass(frozen=True)
class Office:
    id: str
    name: str
    workflows: tuple[str, ...]
    worker: AgentDef
    accent: str = ""

OFFICES: dict[str, Office] = {
    "okfilm": Office(
        "okfilm", "O.K. Film — Production Company / Agency", ("okfilm.production_plan",),
        AgentDef("okfilm-worker", "okfilm", "Production planner",
                 tuple(READ_TOOLS + WRITE_TOOLS + DATE_TOOLS))),
    "institute": Office(
        "institute", "Academic & Art — Subrealism Institute", ("institute.claim_evidence_map",),
        AgentDef("institute-worker", "institute", "Source reader / claim-evidence mapper",
                 tuple(READ_TOOLS + WRITE_TOOLS))),
    "school": Office(
        "school", "Education — School", ("school.lesson",),
        AgentDef("school-worker", "school", "Lesson reviewer / next-task proposer",
                 tuple(READ_TOOLS + WRITE_TOOLS))),
}

WORKFLOW_OFFICE = {w: o.id for o in OFFICES.values() for w in o.workflows}

@dataclass
class AuthContext:
    """Who is really calling, as established by the transport (never by the command body)."""
    principal: str
    offices: frozenset[str]
    actions: frozenset[str]
    simulation_only: bool = False

ALL_ACTIONS = frozenset({"task.create", "task.queue", "approval.decide", "task.cancel",
                         "lesson.attempt", "lesson.finish", "transfer.record"})

def owner() -> AuthContext:
    return AuthContext("owner", frozenset(OFFICES), ALL_ACTIONS)

def agent_ctx(office: str) -> AuthContext:
    # An agent may record work inside its own office; it can never decide approvals.
    return AuthContext(f"agent:{office}", frozenset({office}), frozenset({"transfer.record"}))
