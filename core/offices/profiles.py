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
    workers: dict  # workflow -> AgentDef: one bounded worker role per workflow
    accent: str = ""

    @property
    def workflows(self) -> tuple:
        return tuple(self.workers)

    @property
    def worker(self) -> AgentDef:  # the office's first (default) worker
        return next(iter(self.workers.values()))

_ALL = tuple(READ_TOOLS + WRITE_TOOLS + DATE_TOOLS)
_RW = tuple(READ_TOOLS + WRITE_TOOLS)

OFFICES: dict[str, Office] = {
    "okfilm": Office("okfilm", "O.K. Film und Medienproduktion", {
        "okfilm.production_plan": AgentDef("okfilm-worker", "okfilm", "Project Manager · production plan", _ALL),
        "okfilm.product_brief": AgentDef("okfilm-product-manager", "okfilm", "Product Manager · offer and scope brief", _RW),
        "okfilm.uix_spec": AgentDef("okfilm-uix-designer", "okfilm", "UI/UX Designer · format and readability spec", _RW),
        "okfilm.data_plan": AgentDef("okfilm-data-engineer", "okfilm", "Data Engineer · media and data pipeline plan", _RW),
        "okfilm.edit_plan": AgentDef("okfilm-editor", "okfilm", "Video and Photo Editor · edit plan", _ALL),
        "okfilm.legal_review": AgentDef("okfilm-lawyer", "okfilm", "Lawyer · issue-spotting review (not legal advice)", _ALL),
    }),
    "institute": Office("institute", "Academic & Art — Subrealism Institute", {
        "institute.claim_evidence_map": AgentDef("institute-worker", "institute", "Source reader / claim-evidence mapper", _RW)}),
    "school": Office("school", "Education — School", {
        "school.lesson": AgentDef("school-worker", "school", "Lesson reviewer / next-task proposer", _RW)}),
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
