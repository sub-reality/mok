"""Command handling and read models. The only way to change operational state."""
from __future__ import annotations
import json
from pathlib import Path
from . import SCHEMA_VERSION, contract, lesson
from .profiles import OFFICES, WORKFLOW_OFFICE, AuthContext
from .store import Store, new_id, now, sha256_bytes

class Rejected(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message); self.code = code; self.message = message

def handle(store: Store, command: dict, auth: AuthContext) -> dict:
    """Validate, authorize and apply one command. Never raises for client errors; returns ok=False."""
    problems = contract.validate("command", command)
    if problems:
        return {"ok": False, "error": {"code": "invalid_command", "message": "; ".join(problems[:5])}}
    key = command["idempotency_key"]
    prior = store.one("SELECT result FROM commands WHERE idempotency_key=?", key)
    if prior:
        res = json.loads(prior["result"]); res["duplicate"] = True
        return res
    try:
        result = {"ok": True, "result": _apply(store, command, auth)}
    except Rejected as r:
        result = {"ok": False, "error": {"code": r.code, "message": r.message}}
    result["cursor"] = store.cursor()
    # Rejections caused by a stale version are not memoised: the client may legitimately retry with a new version.
    if result["ok"] or result["error"]["code"] not in ("stale_version",):
        store.q("INSERT INTO commands VALUES(?,?,?,?)", key, command["command_id"], json.dumps(result), now())
    return result

def _authorize(command: dict, auth: AuthContext, store: Store):
    office = command["scope"]["office"]
    if command["action"] not in auth.actions:
        raise Rejected("forbidden_action", f"{auth.principal} may not perform {command['action']}")
    if office not in auth.offices:
        raise Rejected("forbidden_office", f"{auth.principal} has no access to office '{office}'")
    if auth.simulation_only and not store.simulation:
        raise Rejected("forbidden_store", "this caller may only use a rehearsal store")

def _task_for(store: Store, command: dict):
    t = store.task(command["params"]["task_id"])
    if t is None:
        raise Rejected("not_found", "no such task")
    if t["office"] != command["scope"]["office"]:
        raise Rejected("forbidden_office", "task belongs to another office")
    if "expected_version" in command and command["expected_version"] != t["version"]:
        raise Rejected("stale_version", f"task is at version {t['version']}, command expected {command['expected_version']}")
    return t

def _move(store: Store, t, dst: str) -> int:
    if not contract.can_move(t["state"], dst):
        raise Rejected("invalid_transition", f"{t['state']} -> {dst} is not allowed")
    return store.set_state(t["task_id"], dst)

def _apply(store: Store, c: dict, auth: AuthContext) -> dict:
    _authorize(c, auth, store)
    office, action, p = c["scope"]["office"], c["action"], c["params"]
    project = c["scope"].get("project")

    if action == "task.create":
        if WORKFLOW_OFFICE.get(p["workflow"]) != office:
            raise Rejected("workflow_office_mismatch", f"{p['workflow']} does not belong to office '{office}'")
        tid = new_id("task")
        store.q("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", tid, office, project, p["title"], p["workflow"],
                "draft", 1, p.get("due"), p.get("priority"), p.get("kind"),
                json.dumps({"source_packet": p.get("source_packet"), "options": p.get("options", {})}), 0, now(), now())
        store.emit("task.created", office, {"title": p["title"], "workflow": p["workflow"], "due": p.get("due"),
                                             "priority": p.get("priority"), "kind": p.get("kind"), "by": auth.principal},
                   task_id=tid, project=project)
        version = 1
        if p.get("queue"):
            version = store.set_state(tid, "queued")
            store.emit("task.queued", office, {}, task_id=tid, project=project)
        return {"task_id": tid, "version": version, "state": "queued" if p.get("queue") else "draft"}

    if action == "task.queue":
        t = _task_for(store, c)
        v = _move(store, t, "queued")
        store.emit("task.queued", office, {"from": t["state"]}, task_id=t["task_id"], project=t["project"])
        return {"task_id": t["task_id"], "version": v, "state": "queued"}

    if action == "task.cancel":
        t = _task_for(store, c)
        if contract.is_terminal(t["state"]):
            raise Rejected("invalid_transition", f"task is already {t['state']}")
        if t["state"] == "running":
            store.q("UPDATE tasks SET cancel_requested=1, version=version+1, updated_at=? WHERE task_id=?", now(), t["task_id"])
            store.emit("task.cancel_requested", office, {"by": auth.principal}, task_id=t["task_id"], project=t["project"])
            return {"task_id": t["task_id"], "version": t["version"] + 1, "state": "running", "cancel_requested": True}
        v = _move(store, t, "cancelled")
        store.emit("task.cancelled", office, {"by": auth.principal, "acknowledged_by": "core"}, task_id=t["task_id"], project=t["project"])
        return {"task_id": t["task_id"], "version": v, "state": "cancelled"}

    if action == "approval.decide":
        t = _task_for(store, c)
        subject, decision = p["subject"], p["decision"]
        need = "awaiting_review" if subject == "review" else "awaiting_approval"
        if t["state"] != need:
            raise Rejected("invalid_transition", f"task is {t['state']}; a {subject} decision needs {need}")
        if (subject == "review") != (decision in ("accept", "revise")):
            raise Rejected("invalid_command", "review takes accept|revise; action takes approve|reject")
        art = store.latest_artifact(t["task_id"])
        if art is None:
            raise Rejected("no_artifact", "nothing to decide on")
        try:
            current = sha256_bytes(Path(art["path"]).read_bytes())
        except OSError:
            raise Rejected("artifact_missing", "the artifact file is no longer readable")
        if p["artifact_sha256"] != art["sha256"] or current != art["sha256"]:
            raise Rejected("approval_stale", "the artifact changed after it was reviewed; inspect the current version and decide again")
        store.q("INSERT INTO approvals(task_id, subject, decision, destination, artifact_sha256, actor, note, ts) VALUES(?,?,?,?,?,?,?,?)",
                t["task_id"], subject, decision, p.get("destination"), art["sha256"], auth.principal, p.get("note"), now())
        ref = (art["artifact_id"], art["sha256"])
        store.emit("approval.recorded", office, {"subject": subject, "decision": decision, "destination": p.get("destination"),
                                                  "by": auth.principal}, task_id=t["task_id"], project=t["project"], artifact=ref)
        if subject == "review" and decision == "accept":
            v = _move(store, t, "accepted")
            store.emit("task.accepted", office, {"by": auth.principal}, task_id=t["task_id"], project=t["project"], artifact=ref)
            return {"task_id": t["task_id"], "version": v, "state": "accepted"}
        if subject == "review":
            v = _move(store, t, "queued")
            store.emit("task.revision_requested", office, {"note": p.get("note", "")}, task_id=t["task_id"], project=t["project"])
            return {"task_id": t["task_id"], "version": v, "state": "queued"}
        dst = "awaiting_review" if decision == "approve" else "cancelled"
        v = _move(store, t, dst)
        store.emit("task.awaiting_review" if decision == "approve" else "task.cancelled", office, {"by": auth.principal},
                   task_id=t["task_id"], project=t["project"])
        return {"task_id": t["task_id"], "version": v, "state": dst}

    if action == "lesson.attempt":
        return lesson.attempt(store, _task_for(store, c), p)
    if action == "lesson.finish":
        return lesson.finish(store, _task_for(store, c))

    if action == "transfer.record":
        to = p.get("to_office")
        if to not in OFFICES or to == office:
            raise Rejected("invalid_command", "to_office must name another office")
        store.q("INSERT INTO transfers(from_office, to_office, task_id, note, ts) VALUES(?,?,?,?,?)",
                office, to, p.get("task_id"), str(p.get("note", ""))[:500], now())
        store.emit("transfer.recorded", office, {"to_office": to, "note": str(p.get("note", ""))[:200]}, task_id=p.get("task_id"))
        return {"recorded": True}
    raise Rejected("invalid_command", "unknown action")

# -- read models --------------------------------------------------------------

def snapshot(store: Store, auth: AuthContext) -> dict:
    offs = sorted(auth.offices)
    ph = ",".join("?" * len(offs))
    tasks = [{"task_id": r["task_id"], "office": r["office"], "project": r["project"], "title": r["title"],
              "workflow": r["workflow"], "state": r["state"], "version": r["version"], "due": r["due"],
              "priority": r["priority"], "kind": r["kind"], "cancel_requested": bool(r["cancel_requested"]),
              "created_at": r["created_at"], "updated_at": r["updated_at"]}
             for r in store.q(f"SELECT * FROM tasks WHERE office IN ({ph}) ORDER BY created_at", *offs)]
    ids = [t["task_id"] for t in tasks] or [""]
    ph2 = ",".join("?" * len(ids))
    runs = []
    for r in store.q(f"SELECT * FROM runs WHERE task_id IN ({ph2}) ORDER BY started_at", *ids):
        c = store.one("SELECT COUNT(*) n, COALESCE(SUM(ok=0),0) d FROM tool_receipts WHERE run_id=?", r["run_id"])
        runs.append({"run_id": r["run_id"], "task_id": r["task_id"], "agent": r["agent"], "provider": r["provider"],
                     "model_requested": r["model_requested"], "model_served": r["model_served"], "status": r["status"],
                     "started_at": r["started_at"], "ended_at": r["ended_at"], "tool_calls": c["n"], "tool_denials": c["d"],
                     "usage": json.loads(r["usage"]) if r["usage"] else None, "error": r["error"]})
    arts = [{"artifact_id": r["artifact_id"], "task_id": r["task_id"], "run_id": r["run_id"], "name": r["name"],
             "sha256": r["sha256"], "version": r["version"], "bytes": r["bytes"], "created_at": r["created_at"]}
            for r in store.q(f"SELECT * FROM artifacts WHERE task_id IN ({ph2}) ORDER BY created_at", *ids)]
    return {"schema_version": SCHEMA_VERSION, "generated_at": now(), "cursor": store.cursor(),
            "oldest_cursor": store.oldest_cursor(), "simulation": store.simulation,
            "offices": [{"id": o.id, "name": o.name, "workflows": list(o.workflows)} for o in OFFICES.values() if o.id in auth.offices],
            "agents": [{"id": w.id, "office": o.id, "role": w.role, "tools": list(w.tools), "runtime": "claude-agent-sdk | mock"}
                       for o in OFFICES.values() if o.id in auth.offices for w in o.workers.values()],
            "tasks": tasks, "runs": runs, "artifacts": arts}

def events_since(store: Store, auth: AuthContext, since: int, limit: int = 500) -> dict:
    oldest = store.oldest_cursor()
    if oldest and since < oldest - 1:
        return {"ok": False, "error": {"code": "cursor_expired", "message": "take a new snapshot"}, "oldest_cursor": oldest}
    offs = sorted(auth.offices); ph = ",".join("?" * len(offs))
    rows = store.q(f"SELECT * FROM events WHERE cursor>? AND office IN ({ph}) ORDER BY cursor LIMIT ?", since, *offs, limit).fetchall()
    return {"ok": True, "events": [store.event_dict(r) for r in rows], "cursor": rows[-1]["cursor"] if rows else since}

def artifact_body(store: Store, auth: AuthContext, artifact_id: str) -> dict:
    a = store.one("SELECT a.*, t.office FROM artifacts a JOIN tasks t USING(task_id) WHERE artifact_id=?", artifact_id)
    if a is None or a["office"] not in auth.offices:
        return {"ok": False, "error": {"code": "not_found", "message": "no such artifact"}}
    try:
        body = Path(a["path"]).read_bytes()
    except OSError:
        return {"ok": False, "error": {"code": "artifact_missing", "message": "file not readable"}}
    return {"ok": True, "artifact_id": artifact_id, "name": a["name"], "recorded_sha256": a["sha256"],
            "current_sha256": sha256_bytes(body), "unchanged": sha256_bytes(body) == a["sha256"],
            "content": body.decode("utf-8", "replace")}

def task_detail(store: Store, auth: AuthContext, task_id: str) -> dict:
    t = store.task(task_id)
    if t is None or t["office"] not in auth.offices:
        return {"ok": False, "error": {"code": "not_found", "message": "no such task"}}
    snap = snapshot(store, auth)
    runs = [r for r in snap["runs"] if r["task_id"] == task_id]
    return {"ok": True, "task": next(x for x in snap["tasks"] if x["task_id"] == task_id), "runs": runs,
            "artifacts": [a for a in snap["artifacts"] if a["task_id"] == task_id],
            "evidence": [dict(r) for r in store.q("SELECT kind, locator, note, ts FROM evidence WHERE task_id=? ORDER BY id", task_id)],
            "receipts": [dict(r) for r in store.q(
                "SELECT tool, ok, summary, ts FROM tool_receipts WHERE run_id IN (SELECT run_id FROM runs WHERE task_id=?) ORDER BY id", task_id)],
            "approvals": [dict(r) for r in store.q("SELECT subject, decision, destination, artifact_sha256, actor, note, ts FROM approvals WHERE task_id=? ORDER BY id", task_id)]}
