"""Administrative CLI. Everything the manager can do, and running agents, works from here with the manager closed."""
from __future__ import annotations
import argparse, json, os, shutil, sys, uuid
from pathlib import Path
from . import service, executor, providers, lesson
from .profiles import owner, OFFICES
from .store import Store

def _store(a) -> Store:
    d = a.data or os.environ.get("OFFICES_DATA") or (".offices-sim" if a.sim else ".offices")
    return Store(d, simulation=a.sim)

def _cmd(office: str, action: str, params: dict, expected: int | None = None, key: str | None = None) -> dict:
    c = {"command_id": "cmd_" + uuid.uuid4().hex[:16], "idempotency_key": key or "cli_" + uuid.uuid4().hex,
         "actor": {"id": "owner", "client": "cli"}, "scope": {"office": office}, "action": action, "params": params}
    if expected is not None:
        c["expected_version"] = expected
    return c

def _out(x):
    print(json.dumps(x, indent=2, ensure_ascii=False, default=str))
    return 0 if not isinstance(x, dict) or x.get("ok", True) else 1

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="offices", description="Agentic AI Offices — administrative interface")
    ap.add_argument("--data", help="data directory (default .offices, or .offices-sim with --sim)")
    ap.add_argument("--sim", action="store_true", help="use the isolated rehearsal store (mock provider only)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("packet", help="copy a folder of approved source files into an office's source root")
    s.add_argument("office", choices=list(OFFICES)); s.add_argument("folder"); s.add_argument("--name")

    s = sub.add_parser("create", help="create a task")
    s.add_argument("office", choices=list(OFFICES)); s.add_argument("workflow"); s.add_argument("title")
    s.add_argument("--packet"); s.add_argument("--due"); s.add_argument("--priority"); s.add_argument("--kind")
    s.add_argument("--as-of"); s.add_argument("--deck"); s.add_argument("--mode", default="socratic")
    s.add_argument("--max-cards", type=int, default=5); s.add_argument("--queue", action="store_true"); s.add_argument("--key")

    s = sub.add_parser("queue"); s.add_argument("task_id")
    s = sub.add_parser("run", help="run a queued task with a provider up to the review boundary")
    s.add_argument("task_id"); s.add_argument("--provider", choices=["mock", "claude"], required=True)
    s.add_argument("--model", default=providers.TARGET_MODEL)
    s = sub.add_parser("show"); s.add_argument("task_id")
    s = sub.add_parser("list")
    s = sub.add_parser("events"); s.add_argument("--since", type=int, default=0)
    s = sub.add_parser("artifact"); s.add_argument("artifact_id")
    s = sub.add_parser("review", help="human decision on the reviewed artifact version")
    s.add_argument("task_id"); s.add_argument("decision", choices=["accept", "revise"]); s.add_argument("--sha", required=True)
    s.add_argument("--note", default="")
    s = sub.add_parser("cancel"); s.add_argument("task_id")
    s = sub.add_parser("lesson", help="run a School lesson interactively in the terminal"); s.add_argument("task_id")
    s = sub.add_parser("snapshot")
    s = sub.add_parser("export-fixture", help="write a sanitised snapshot + event recording for presentation clients")
    s.add_argument("out")
    s = sub.add_parser("serve", help="local read/command API for the manager (127.0.0.1 only)")
    s.add_argument("--port", type=int, default=8787); s.add_argument("--origin", default="http://localhost:8080")
    a = ap.parse_args(argv)
    st, auth = _store(a), owner()

    def task_office(tid):
        t = st.task(tid)
        if t is None:
            print("no such task", file=sys.stderr); sys.exit(1)
        return t

    if a.cmd == "packet":
        src = Path(a.folder)
        dst = st.source_root(a.office) / (a.name or src.name)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return _out({"ok": True, "packet": dst.name, "files": sorted(p.name for p in dst.iterdir())})
    if a.cmd == "create":
        p = {"title": a.title, "workflow": a.workflow, "queue": a.queue}
        for k, v in (("source_packet", a.packet), ("due", a.due), ("priority", a.priority), ("kind", a.kind)):
            if v: p[k] = v
        opts = {}
        if a.as_of: opts["as_of"] = a.as_of
        if a.deck: opts.update(deck=a.deck, mode=a.mode, max_cards=a.max_cards)
        if opts: p["options"] = opts
        return _out(service.handle(st, _cmd(a.office, "task.create", p, key=a.key), auth))
    if a.cmd == "queue":
        t = task_office(a.task_id)
        return _out(service.handle(st, _cmd(t["office"], "task.queue", {"task_id": a.task_id}, t["version"]), auth))
    if a.cmd == "run":
        prov = providers.get(a.provider, **({"model": a.model} if a.provider == "claude" else {}))
        try:
            return _out({"ok": True, **executor.run_task(st, a.task_id, prov)})
        except executor.NotRunnable as e:
            return _out({"ok": False, "error": {"code": "not_runnable", "message": str(e)}})
    if a.cmd == "show":
        return _out(service.task_detail(st, auth, a.task_id))
    if a.cmd == "list":
        for t in service.snapshot(st, auth)["tasks"]:
            print(f"{t['task_id']}  {t['office']:<9} {t['state']:<16} v{t['version']:<3} due {t['due'] or '-':<10} {t['title']}")
        return 0
    if a.cmd == "events":
        return _out(service.events_since(st, auth, a.since))
    if a.cmd == "artifact":
        r = service.artifact_body(st, auth, a.artifact_id)
        if r["ok"]:
            print(f"# {r['name']}  sha256 {r['recorded_sha256']}  unchanged={r['unchanged']}\n"); print(r["content"]); return 0
        return _out(r)
    if a.cmd == "review":
        t = task_office(a.task_id)
        return _out(service.handle(st, _cmd(t["office"], "approval.decide", {"task_id": a.task_id, "subject": "review",
                    "decision": a.decision, "artifact_sha256": a.sha, "note": a.note}, t["version"]), auth))
    if a.cmd == "cancel":
        t = task_office(a.task_id)
        return _out(service.handle(st, _cmd(t["office"], "task.cancel", {"task_id": a.task_id}, t["version"]), auth))
    if a.cmd == "lesson":
        t = task_office(a.task_id)
        while True:
            t = st.task(a.task_id)
            card = lesson.next_card(st, t) if t["state"] in ("queued", "running") else None
            if card is None:
                break
            print(f"\n{card['prompt']}")
            for h in card["hints_shown"]: print(f"  ipucu: {h}")
            ans = input("> (boş = ipucu, :q = bitir) ").strip()
            if ans == ":q": break
            p = {"task_id": a.task_id, "card_id": card["card_id"], **({"hint": True} if not ans else {"answer": ans})}
            r = service.handle(st, _cmd("school", "lesson.attempt", p), auth)
            res = r.get("result", r.get("error"))
            print({k: v for k, v in res.items() if k not in ("next", "version")})
        t = st.task(a.task_id)
        if t["state"] == "running":
            return _out(service.handle(st, _cmd("school", "lesson.finish", {"task_id": a.task_id}, t["version"]), auth))
        return 0
    if a.cmd == "snapshot":
        return _out(service.snapshot(st, auth))
    if a.cmd == "export-fixture":
        snap = service.snapshot(st, auth)
        ev = service.events_since(st, auth, 0, limit=5000)["events"]
        details, bodies = {}, {}
        for t in snap["tasks"]:
            d = service.task_detail(st, auth, t["task_id"])
            private = t["office"] == "school"   # learner records never leave the core
            details[t["task_id"]] = {"evidence": [] if private else [{k: e[k] for k in ("kind", "locator", "note")} for e in d["evidence"]]}
            if not private:
                for art in d["artifacts"][-1:]:
                    bodies[art["artifact_id"]] = service.artifact_body(st, auth, art["artifact_id"])["content"]
        Path(a.out).write_text(json.dumps({"snapshot": snap, "events": ev, "details": details, "bodies": bodies},
                                          indent=1, ensure_ascii=False), "utf-8")
        return _out({"ok": True, "tasks": len(snap["tasks"]), "events": len(ev), "out": a.out})
    if a.cmd == "serve":
        from . import api
        return api.serve(st, a.port, a.origin, os.environ.get('OFFICES_API_TOKEN'))
    return 2

if __name__ == "__main__":
    sys.exit(main())
