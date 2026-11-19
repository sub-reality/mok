"""Inference providers behind one replaceable adapter. Every run records which one was used."""
from __future__ import annotations
import asyncio, re
from dataclasses import dataclass, field
from .toolbox import Toolbox, SPECS, Cancelled, BudgetExhausted

TARGET_MODEL = "claude-fable-5-2"

@dataclass
class RunResult:
    provider: str
    model_requested: str | None
    model_served: str | None = None
    usage: dict = field(default_factory=dict)
    final_text: str = ""
    error: str | None = None

class MockProvider:
    """Deterministic, fixture-driven stand-in. It performs NO model inference and says so in its artifact."""
    name = "mock"
    def run(self, task, toolbox: Toolbox, system_prompt: str, user_prompt: str) -> RunResult:
        ok, listing = toolbox.call("list_sources", {})
        names = [l.split("\t")[0] for l in listing.splitlines()] if ok else []
        dated = []
        for n in names:
            ok, text = toolbox.call("read_source", {"name": n})
            if not ok:
                continue
            for line in text.splitlines():
                m = re.match(r"\s*(\d+)\|.*?(\d{4}-\d{2}-\d{2})", line)
                if m:
                    toolbox.call("record_evidence", {"kind": "fact", "locator": f"{n}:{m.group(1)}", "note": f"date {m.group(2)}"})
                    dated.append((m.group(2), n, m.group(1)))
        toolbox.call("report_missing", {"question": "MOCK RUN: no model read these sources; nothing was interpreted."})
        out_name = {"okfilm.production_plan": "production-plan.md", "institute.claim_evidence_map": "claim-evidence-map.md",
                    "school.lesson": "next-retrieval.md"}.get(task["workflow"], task["workflow"].split(".")[1].replace("_", "-") + ".md")
        body = [f"# MOCK ARTIFACT — {task['title']}", "",
                "> Produced by the mock provider from fixtures. **No model inference took place.** Do not review this as real work.", "",
                "## Inputs read", *[f"- {n}" for n in names], "", "## Dates found by pattern match",
                *[f"- {d} ({n}:{l})" for d, n, l in sorted(dated)], ""]
        toolbox.call("write_artifact", {"name": out_name, "content": "\n".join(body)})
        return RunResult("mock", None, None, {"tool_calls": toolbox.calls}, "mock run finished")

class ClaudeProvider:
    """Real agent loop through the Claude Agent SDK. Only the office tools are exposed; built-in tools are disabled."""
    name = "claude"
    def __init__(self, model: str = TARGET_MODEL, max_budget_usd: float | None = 3.0):
        self.model, self.max_budget_usd = model, max_budget_usd

    def run(self, task, toolbox: Toolbox, system_prompt: str, user_prompt: str) -> RunResult:
        return asyncio.run(self._run(toolbox, system_prompt, user_prompt))

    async def _run(self, toolbox: Toolbox, system_prompt: str, user_prompt: str) -> RunResult:
        from claude_agent_sdk import (query, ClaudeAgentOptions, tool, create_sdk_mcp_server,
                                      AssistantMessage, ResultMessage, TextBlock)
        res = RunResult("claude", self.model)
        stop: dict = {}

        def make(name: str):
            desc, schema = SPECS[name]
            @tool(name, desc, schema)
            async def handler(args):
                if stop:
                    return {"content": [{"type": "text", "text": "STOP: the run has been halted. Reply 'stopped' and end."}], "is_error": True}
                try:
                    ok, out = toolbox.call(name, args)
                except Cancelled:
                    stop["why"] = "cancelled"
                    return {"content": [{"type": "text", "text": "STOP: cancellation was requested. Reply 'stopped' and end."}], "is_error": True}
                except BudgetExhausted:
                    stop["why"] = "budget_exhausted"
                    return {"content": [{"type": "text", "text": "STOP: tool budget exhausted. Reply 'stopped' and end."}], "is_error": True}
                return {"content": [{"type": "text", "text": out}], "is_error": not ok}
            return handler

        names = toolbox.allowed()
        server = create_sdk_mcp_server("office", tools=[make(n) for n in names])
        opts = ClaudeAgentOptions(
            model=self.model, system_prompt=system_prompt, mcp_servers={"office": server}, strict_mcp_config=True,
            tools=[], allowed_tools=[f"mcp__office__{n}" for n in names], setting_sources=[],
            max_turns=toolbox.agent.max_turns, max_budget_usd=self.max_budget_usd, cwd=str(toolbox.out))

        async def prompt_stream():
            yield {"type": "user", "message": {"role": "user", "content": user_prompt}}

        served = set()
        try:
            async for m in query(prompt=prompt_stream(), options=opts):
                if isinstance(m, AssistantMessage):
                    if m.model:
                        served.add(m.model)
                    for b in m.content:
                        if isinstance(b, TextBlock):
                            res.final_text = b.text
                elif isinstance(m, ResultMessage):
                    res.usage = {"num_turns": m.num_turns, "duration_ms": m.duration_ms,
                                 "total_cost_usd_estimate": m.total_cost_usd, "tokens": m.usage}
                    if m.is_error:
                        res.error = f"runtime_error:{m.subtype}"
        except Exception as e:  # runtime/transport failure is a failed run, never a silent success
            res.error = f"runtime_exception:{e.__class__.__name__}: {str(e)[:200]}"
        res.model_served = ",".join(sorted(served)) or None
        if stop:
            res.error = stop["why"]
        elif served and served != {self.model} and not res.error:
            res.error = f"model_substituted: requested {self.model}, served {res.model_served}"
        return res

def get(name: str, **kw):
    if name == "mock":
        return MockProvider()
    if name == "claude":
        return ClaudeProvider(**kw)
    raise ValueError(f"unknown provider '{name}'")
