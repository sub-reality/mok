"""School: a bounded lesson. Checking is deterministic; the agent only reviews the recorded attempts afterwards."""
from __future__ import annotations
import json, re, shutil
from .store import Store, new_id, now

def normalise(s: str) -> list[str]:
    s = s.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("’", "'")):
        s = s.replace(a, b)
    return re.findall(r"[a-z0-9']+", s)

def _deck(store: Store, task) -> list[dict]:
    from .service import Rejected
    params = json.loads(task["params"])
    name = params.get("options", {}).get("deck", "")
    if not re.match(r"^[A-Za-z0-9._-]{1,80}\.json$", name):
        raise Rejected("invalid_command", "lesson task has no valid deck")
    p = store.source_root("school") / "decks" / name
    if not p.is_file():
        raise Rejected("not_found", f"deck '{name}' is not in the School's approved decks")
    cards = json.loads(p.read_text("utf-8"))
    limit = int(params.get("options", {}).get("max_cards", 5))
    return cards[:max(1, min(limit, 20))]

def next_card(store: Store, task) -> dict | None:
    done = {r["card_id"] for r in store.q("SELECT card_id FROM lesson_attempts WHERE task_id=? AND correct=1", task["task_id"])}
    for c in _deck(store, task):
        if c["id"] not in done:
            level = store.one("SELECT COALESCE(MAX(hint_level),0) h FROM lesson_attempts WHERE task_id=? AND card_id=?",
                              task["task_id"], c["id"])["h"]
            return {"card_id": c["id"], "prompt": c["prompt"], "hints_shown": c.get("hints", [])[:level]}
    return None

def attempt(store: Store, task, p: dict) -> dict:
    from .service import Rejected
    if task["state"] == "queued":
        run_id = new_id("run")
        store.set_state(task["task_id"], "running")
        store.q("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)", run_id, task["task_id"], "learner", "interactive", None, None,
                "running", now(), None, None, None)
        store.emit("run.started", "school", {"agent": "learner", "provider": "interactive"}, task_id=task["task_id"], run_id=run_id)
    elif task["state"] != "running":
        raise Rejected("invalid_transition", f"lesson is {task['state']}")
    cur = next_card(store, task)
    if cur is None:
        raise Rejected("lesson_complete", "all cards answered; send lesson.finish")
    if p["card_id"] != cur["card_id"]:
        raise Rejected("wrong_card", f"one prompt at a time: the current card is {cur['card_id']}")
    card = next(c for c in _deck(store, task) if c["id"] == cur["card_id"])
    mode = json.loads(task["params"]).get("options", {}).get("mode", "socratic")
    level = len(cur["hints_shown"])
    hints = card.get("hints", [])
    out: dict = {"card_id": card["id"], "mode": mode}
    if p.get("hint"):
        if mode != "socratic":
            raise Rejected("invalid_command", "hints belong to socratic mode; direct mode shows the correction after an attempt")
        level = min(level + 1, len(hints))
        store.q("INSERT INTO lesson_attempts(task_id, card_id, answer, correct, hint_level, mode, ts) VALUES(?,?,?,?,?,?,?)",
                task["task_id"], card["id"], None, 0, level, mode, now())
        out.update(correct=None, hint=hints[level - 1] if level else None, hints_left=len(hints) - level)
    else:
        correct = normalise(p.get("answer", "")) == normalise(card["answer"])
        store.q("INSERT INTO lesson_attempts(task_id, card_id, answer, correct, hint_level, mode, ts) VALUES(?,?,?,?,?,?,?)",
                task["task_id"], card["id"], p.get("answer", "")[:1000], int(correct), level, mode, now())
        out["correct"] = correct
        if not correct and mode == "direct":
            out["correction"] = card["answer"]
        elif not correct:
            out["hints_left"] = len(hints) - level  # socratic: the learner gets another try before any answer is shown
    store.emit("lesson.attempt_recorded", "school", {"card_id": card["id"], "correct": out.get("correct"), "hint_level": level},
               task_id=task["task_id"])
    nxt = next_card(store, store.task(task["task_id"]))
    out["next"] = nxt
    out["version"] = store.task(task["task_id"])["version"]
    return out

def finish(store: Store, task) -> dict:
    """Close the interactive part: write the attempt log as a source packet and queue the review run."""
    from .service import Rejected
    if task["state"] != "running":
        raise Rejected("invalid_transition", f"lesson is {task['state']}")
    rows = [dict(r) for r in store.q("SELECT card_id, answer, correct, hint_level, mode, ts FROM lesson_attempts WHERE task_id=? ORDER BY id", task["task_id"])]
    packet = f"lesson-{task['task_id']}"
    d = store.source_root("school") / packet
    d.mkdir(parents=True, exist_ok=True)
    (d / "attempts.json").write_text("[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n]\n", "utf-8")
    (d / "deck.json").write_text("[\n" + ",\n".join(json.dumps(c, ensure_ascii=False) for c in _deck(store, task)) + "\n]\n", "utf-8")
    params = json.loads(task["params"]); params["source_packet"] = packet
    store.q("UPDATE tasks SET params=? WHERE task_id=?", json.dumps(params), task["task_id"])
    run = store.one("SELECT run_id FROM runs WHERE task_id=? AND provider='interactive' AND status='running'", task["task_id"])
    if run:
        store.q("UPDATE runs SET status='completed', ended_at=? WHERE run_id=?", now(), run["run_id"])
    store.set_state(task["task_id"], "queued")  # contract rule 'lesson_handoff'
    store.emit("task.queued", "school", {"from": "running", "reason": "lesson finished; review run pending",
                                          "attempts": len([r for r in rows if r["answer"] is not None]),
                                          "hints": len([r for r in rows if r["answer"] is None])}, task_id=task["task_id"])
    return {"task_id": task["task_id"], "state": "queued", "version": store.task(task["task_id"])["version"], "attempts": len(rows)}
