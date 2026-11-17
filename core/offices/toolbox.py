"""The executor-side tools an agent may call. Permissions are enforced here, in code, not in prompts."""
from __future__ import annotations
import json, re
from datetime import date, timedelta
from pathlib import Path
from .profiles import AgentDef
from .store import Store, new_id, now, sha256_bytes

class Cancelled(Exception): ...
class BudgetExhausted(Exception): ...

MAX_READ_BYTES = 60_000
MAX_ARTIFACT_BYTES = 200_000
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")

SPECS = {
    "list_sources": ("List the files in this task's approved source packet.", {}),
    "read_source": ("Read one file from the approved source packet. Returns numbered lines so you can cite 'file:line'.",
                    {"name": str}),
    "date_math": ("Deterministic date arithmetic. op='days_between' needs a and b (YYYY-MM-DD); op='add_days' needs a and days; "
                  "op='weekday' needs a. Always use this instead of computing dates yourself.",
                  {"op": str, "a": str, "b": str, "days": int}),
    "record_evidence": ("Record one piece of evidence: kind is 'quote', 'fact', 'interpretation' or 'hypothesis'; "
                        "locator is 'file:line' for quote/fact.", {"kind": str, "locator": str, "note": str}),
    "report_missing": ("Record a piece of information that is missing from the sources and must be supplied by the owner.",
                       {"question": str}),
    "write_artifact": ("Write the deliverable as a UTF-8 text/Markdown file into this task's output folder. "
                       "Calling it again with the same name creates a new version.", {"name": str, "content": str}),
}

class Toolbox:
    def __init__(self, store: Store, task, run_id: str, agent: AgentDef):
        self.store, self.task, self.run_id, self.agent = store, task, run_id, agent
        self.office = task["office"]
        params = json.loads(task["params"])
        packet = params.get("source_packet")
        root = store.source_root(self.office)
        self.src = (root / packet).resolve() if packet else None
        if self.src is not None and (root.resolve() not in self.src.parents or not self.src.is_dir()):
            self.src = None
        self.out = store.artifact_dir(self.office, task["task_id"]).resolve()
        self.calls = 0
        self.as_of = params.get("options", {}).get("as_of")

    def allowed(self) -> list[str]:
        return [t for t in self.agent.tools if t in SPECS]

    # -- single entry point: every call is checked and receipted -------
    def call(self, tool: str, args: dict) -> tuple[bool, str]:
        t = self.store.task(self.task["task_id"])
        if t["cancel_requested"]:
            raise Cancelled()
        self.calls += 1
        if self.calls > self.agent.max_tool_calls:
            raise BudgetExhausted()
        if tool not in self.agent.tools or tool not in SPECS:
            ok, out = False, f"DENIED: tool '{tool}' is not permitted for {self.agent.id}"
        else:
            try:
                ok, out = getattr(self, "_" + tool)(**{k: v for k, v in (args or {}).items() if k in SPECS[tool][1]})
            except TypeError as e:
                ok, out = False, f"ERROR: bad arguments ({e})"
            except OSError as e:
                ok, out = False, f"ERROR: {e.__class__.__name__}"
        brief = {k: (v if len(str(v)) <= 120 else str(v)[:117] + "...") for k, v in (args or {}).items() if k != "content"}
        self.store.q("INSERT INTO tool_receipts(run_id, tool, input, ok, summary, ts) VALUES(?,?,?,?,?,?)",
                     self.run_id, tool, json.dumps(brief), int(ok), out[:200], now())
        self.store.emit("tool.called", self.office, {"tool": tool, "ok": ok}, task_id=self.task["task_id"], run_id=self.run_id)
        return ok, out

    def _inside(self, base: Path, name: str) -> Path | None:
        if base is None or not NAME_RE.match(name or ""):
            return None
        p = (base / name).resolve()
        return p if p.parent == base else None

    def _list_sources(self):
        if self.src is None:
            return False, "DENIED: this task has no approved source packet"
        return True, "\n".join(sorted(f"{p.name}\t{p.stat().st_size} bytes" for p in self.src.iterdir() if p.is_file())) or "(empty)"

    def _read_source(self, name: str = ""):
        p = self._inside(self.src, name)
        if p is None or not p.is_file():
            return False, f"DENIED: '{name}' is not a file inside this task's source packet"
        text = p.read_bytes()[:MAX_READ_BYTES].decode("utf-8", "replace")
        return True, "\n".join(f"{i+1:>4}| {line}" for i, line in enumerate(text.splitlines()))

    def _date_math(self, op: str = "", a: str = "", b: str = "", days: int = 0):
        try:
            da = date.fromisoformat(a)
            if op == "days_between":
                return True, str((date.fromisoformat(b) - da).days)
            if op == "add_days":
                return True, (da + timedelta(days=int(days))).isoformat()
            if op == "weekday":
                return True, da.strftime("%A")
        except (ValueError, TypeError):
            return False, "ERROR: dates must be YYYY-MM-DD"
        return False, "ERROR: op must be days_between, add_days or weekday"

    def _record_evidence(self, kind: str = "", locator: str = "", note: str = ""):
        if kind not in ("quote", "fact", "interpretation", "hypothesis"):
            return False, "ERROR: kind must be quote, fact, interpretation or hypothesis"
        if kind in ("quote", "fact"):
            m = re.match(r"^([A-Za-z0-9._-]+):(\d+)", locator or "")
            p = self._inside(self.src, m.group(1)) if m else None
            if p is None or not p.is_file():
                return False, "ERROR: quote/fact needs a locator 'file:line' pointing into the source packet"
            lines = p.read_text("utf-8", "replace").splitlines()
            if not 1 <= int(m.group(2)) <= len(lines):
                return False, "ERROR: that line does not exist in the file"
        self.store.q("INSERT INTO evidence(task_id, run_id, kind, locator, note, ts) VALUES(?,?,?,?,?,?)",
                     self.task["task_id"], self.run_id, kind, (locator or "")[:120], (note or "")[:600], now())
        self.store.emit("evidence.recorded", self.office, {"kind": kind, "locator": (locator or "")[:120]},
                        task_id=self.task["task_id"], run_id=self.run_id)
        return True, "recorded"

    def _report_missing(self, question: str = ""):
        if not question.strip():
            return False, "ERROR: empty question"
        self.store.q("INSERT INTO evidence(task_id, run_id, kind, locator, note, ts) VALUES(?,?,?,?,?,?)",
                     self.task["task_id"], self.run_id, "missing_info", "", question[:600], now())
        self.store.emit("evidence.recorded", self.office, {"kind": "missing_info"}, task_id=self.task["task_id"], run_id=self.run_id)
        return True, "recorded"

    def _write_artifact(self, name: str = "", content: str = ""):
        p = self._inside(self.out, name)
        if p is None or not name.lower().endswith((".md", ".txt", ".json", ".csv")):
            return False, "DENIED: artifact name must be a plain .md/.txt/.json/.csv file name"
        data = content.encode("utf-8")
        if not data or len(data) > MAX_ARTIFACT_BYTES:
            return False, "ERROR: artifact is empty or too large"
        p.write_bytes(data)
        version = self.store.one("SELECT COUNT(*) n FROM artifacts WHERE task_id=? AND name=?", self.task["task_id"], name)["n"] + 1
        aid, sha = new_id("art"), sha256_bytes(data)
        self.store.q("INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?)", aid, self.task["task_id"], self.run_id, name, str(p),
                     sha, len(data), version, now())
        self.store.emit("artifact.written", self.office, {"name": name, "version": version, "bytes": len(data)},
                        task_id=self.task["task_id"], run_id=self.run_id, artifact=(aid, sha))
        return True, f"written {name} v{version} ({len(data)} bytes, sha256 {sha[:12]}…)"
