"""Contract v0.1: schema validation and the task state machine."""
from __future__ import annotations
import json, os
from functools import lru_cache
from pathlib import Path
import jsonschema

def contract_dir() -> Path:
    env = os.environ.get("OFFICES_CONTRACT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "contract" / "v0.1"

@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return json.loads((contract_dir() / name).read_text(encoding="utf-8"))

def _validator(name: str):
    return jsonschema.Draft202012Validator(_load(name), format_checker=jsonschema.FormatChecker())

def validate(kind: str, obj: dict) -> list[str]:
    """Return a list of human-readable problems (empty when valid)."""
    v = _validator(f"{kind}.schema.json")
    return [f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in v.iter_errors(obj)]

def transitions() -> dict:
    return _load("transitions.json")

def can_move(src: str, dst: str) -> bool:
    return dst in transitions()["transitions"].get(src, [])

def is_terminal(state: str) -> bool:
    return state in transitions()["terminal"]
