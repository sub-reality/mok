"""SQLite store: the single authoritative record of tasks, runs, artifacts, evidence, approvals, events."""
from __future__ import annotations
import hashlib, json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from . import SCHEMA_VERSION

DDL = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS tasks(
  task_id TEXT PRIMARY KEY, office TEXT NOT NULL, project TEXT, title TEXT NOT NULL, workflow TEXT NOT NULL,
  state TEXT NOT NULL, version INTEGER NOT NULL, due TEXT, priority TEXT, kind TEXT,
  params TEXT NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, agent TEXT, provider TEXT, model_requested TEXT, model_served TEXT,
  status TEXT, started_at TEXT, ended_at TEXT, usage TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS tool_receipts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, tool TEXT, input TEXT, ok INTEGER, summary TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS artifacts(
  artifact_id TEXT PRIMARY KEY, task_id TEXT, run_id TEXT, name TEXT, path TEXT, sha256 TEXT, bytes INTEGER,
  version INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS evidence(
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, run_id TEXT, kind TEXT, locator TEXT, note TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS approvals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, subject TEXT, decision TEXT, destination TEXT,
  artifact_sha256 TEXT, actor TEXT, note TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS transfers(
  id INTEGER PRIMARY KEY AUTOINCREMENT, from_office TEXT, to_office TEXT, task_id TEXT, note TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS lesson_attempts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, card_id TEXT, answer TEXT, correct INTEGER,
  hint_level INTEGER, mode TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS events(
  cursor INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT, ts TEXT, office TEXT, project TEXT, task_id TEXT,
  run_id TEXT, type TEXT, payload TEXT, artifact_id TEXT, artifact_sha TEXT);
CREATE TABLE IF NOT EXISTS commands(idempotency_key TEXT PRIMARY KEY, command_id TEXT, result TEXT, ts TEXT);
"""

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

class Store:
    def __init__(self, data_dir: str | Path, simulation: bool = False):
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.data_dir / "offices.db", isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(DDL)
        row = self.db.execute("SELECT value FROM meta WHERE key='simulation'").fetchone()
        if row is None:
            self.db.execute("INSERT INTO meta VALUES('simulation', ?)", ("1" if simulation else "0",))
            self.simulation = simulation
        else:
            self.simulation = row["value"] == "1"
            if simulation != self.simulation:
                raise RuntimeError("store simulation flag mismatch: a live store cannot be opened as a rehearsal store or vice versa")

    # -- paths ---------------------------------------------------------
    def source_root(self, office: str) -> Path:
        p = self.data_dir / office / "sources"; p.mkdir(parents=True, exist_ok=True); return p
    def artifact_dir(self, office: str, task_id: str) -> Path:
        p = self.data_dir / office / "artifacts" / task_id; p.mkdir(parents=True, exist_ok=True); return p

    # -- generic -------------------------------------------------------
    def q(self, sql: str, *a):
        return self.db.execute(sql, a)
    def one(self, sql: str, *a):
        return self.db.execute(sql, a).fetchone()

    def emit(self, type_: str, office: str, payload: dict | None = None, *, task_id=None, run_id=None,
             project=None, artifact: tuple[str, str] | None = None) -> int:
        cur = self.q(
            "INSERT INTO events(event_id, ts, office, project, task_id, run_id, type, payload, artifact_id, artifact_sha)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            new_id("evt"), now(), office, project, task_id, run_id, type_, json.dumps(payload or {}),
            artifact[0] if artifact else None, artifact[1] if artifact else None)
        return cur.lastrowid

    def event_dict(self, r) -> dict:
        e = {"event_id": r["event_id"], "schema_version": SCHEMA_VERSION, "cursor": r["cursor"], "ts": r["ts"],
             "office": r["office"], "project": r["project"], "task_id": r["task_id"], "run_id": r["run_id"],
             "type": r["type"], "simulation": self.simulation, "payload": json.loads(r["payload"])}
        if r["artifact_id"]:
            e["artifact_ref"] = {"artifact_id": r["artifact_id"], "sha256": r["artifact_sha"]}
        return e

    def cursor(self) -> int:
        return self.one("SELECT COALESCE(MAX(cursor),0) c FROM events")["c"]
    def oldest_cursor(self) -> int:
        return self.one("SELECT COALESCE(MIN(cursor),0) c FROM events")["c"]

    def task(self, task_id: str):
        return self.one("SELECT * FROM tasks WHERE task_id=?", task_id)

    def set_state(self, task_id: str, state: str) -> int:
        self.q("UPDATE tasks SET state=?, version=version+1, updated_at=? WHERE task_id=?", state, now(), task_id)
        return self.task(task_id)["version"]

    def latest_artifact(self, task_id: str):
        return self.one("SELECT * FROM artifacts WHERE task_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1", task_id)
