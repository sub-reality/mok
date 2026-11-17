"""Runs one queued task through a provider up to the review boundary."""
from __future__ import annotations
import json
from . import contract, workflows
from .profiles import OFFICES
from .providers import RunResult
from .store import Store, new_id, now
from .toolbox import Toolbox, Cancelled, BudgetExhausted

class NotRunnable(Exception): ...

def run_task(store: Store, task_id: str, provider) -> dict:
    task = store.task(task_id)
    if task is None:
        raise NotRunnable("no such task")
    if task["state"] != "queued":
        raise NotRunnable(f"task is {task['state']}, not queued")
    if store.simulation and provider.name != "mock":
        raise NotRunnable("a rehearsal store never gets live inference or live tools; use the mock provider")
    office = OFFICES[task["office"]]
    agent = office.worker
    run_id = new_id("run")
    store.set_state(task_id, "running")
    store.q("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)", run_id, task_id, agent.id, provider.name,
            getattr(provider, "model", None), None, "running", now(), None, None, None)
    store.emit("run.started", office.id, {"agent": agent.id, "provider": provider.name,
                                           "model_requested": getattr(provider, "model", None)},
               task_id=task_id, run_id=run_id, project=task["project"])
    task = store.task(task_id)
    box = Toolbox(store, task, run_id, agent)
    try:
        res: RunResult = provider.run(task, box, workflows.system_prompt(task), workflows.user_prompt(task))
    except Cancelled:
        res = RunResult(provider.name, getattr(provider, "model", None), error="cancelled")
    except BudgetExhausted:
        res = RunResult(provider.name, getattr(provider, "model", None), error="budget_exhausted")
    return finish_run(store, task_id, run_id, res)

def finish_run(store: Store, task_id: str, run_id: str, res: RunResult) -> dict:
    task = store.task(task_id)
    office = task["office"]
    art = store.one("SELECT * FROM artifacts WHERE run_id=? ORDER BY rowid DESC LIMIT 1", run_id)
    if res.error is None and art is None:
        res.error = "no_artifact: the worker stopped without writing a deliverable"
    usage = json.dumps(res.usage, default=str)
    if res.error == "cancelled" or (task["cancel_requested"] and res.error):
        store.q("UPDATE runs SET status='cancelled', ended_at=?, usage=?, error=?, model_served=? WHERE run_id=?",
                now(), usage, "cancelled", res.model_served, run_id)
        store.q("UPDATE tasks SET cancel_requested=0 WHERE task_id=?", task_id)
        store.set_state(task_id, "cancelled")
        store.emit("task.cancelled", office, {"acknowledged_by": "worker"}, task_id=task_id, run_id=run_id, project=task["project"])
        return {"run_id": run_id, "status": "cancelled", "state": "cancelled"}
    if res.error:
        store.q("UPDATE runs SET status='failed', ended_at=?, usage=?, error=?, model_served=? WHERE run_id=?",
                now(), usage, res.error, res.model_served, run_id)
        store.set_state(task_id, "failed")
        store.emit("run.failed", office, {"error": res.error[:200], "provider": res.provider}, task_id=task_id, run_id=run_id,
                   project=task["project"])
        return {"run_id": run_id, "status": "failed", "state": "failed", "error": res.error}
    store.q("UPDATE runs SET status='completed', ended_at=?, usage=?, model_served=? WHERE run_id=?",
            now(), usage, res.model_served, run_id)
    ref = (art["artifact_id"], art["sha256"])
    store.emit("run.completed", office, {"provider": res.provider, "model_served": res.model_served}, task_id=task_id,
               run_id=run_id, project=task["project"], artifact=ref)
    store.set_state(task_id, "awaiting_review")
    store.emit("task.awaiting_review", office, {}, task_id=task_id, run_id=run_id, project=task["project"], artifact=ref)
    return {"run_id": run_id, "status": "completed", "state": "awaiting_review", "artifact_id": art["artifact_id"],
            "sha256": art["sha256"], "provider": res.provider, "model_served": res.model_served}
