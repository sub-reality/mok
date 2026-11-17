"""Local HTTP adapter for presentation clients. Binds 127.0.0.1, bearer token, one allowed origin.
It exposes only the redacted read models and the validated command endpoint; it never runs agents."""
from __future__ import annotations
import json, secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from . import service
from .profiles import owner
from .store import Store

def make_handler(store: Store, token: str, origin: str):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _send(self, code: int, body: dict):
            data = json.dumps(body, ensure_ascii=False, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers(); self.wfile.write(data)
        def _auth(self):
            if secrets.compare_digest(self.headers.get("Authorization", ""), f"Bearer {token}"):
                return owner()  # the token holder is the single owner; the command body cannot widen this
            self._send(401, {"ok": False, "error": {"code": "unauthenticated", "message": "bearer token required"}})
            return None
        def do_OPTIONS(self): self._send(204, {})
        def do_GET(self):
            auth = self._auth()
            if not auth: return
            u = urlparse(self.path); q = parse_qs(u.query)
            if u.path == "/v0/snapshot":
                return self._send(200, service.snapshot(store, auth))
            if u.path == "/v0/events":
                try: since = int(q.get("since", ["0"])[0])
                except ValueError: return self._send(400, {"ok": False, "error": {"code": "invalid", "message": "since must be an integer"}})
                r = service.events_since(store, auth, since); return self._send(200 if r["ok"] else 410, r)
            if u.path.startswith("/v0/tasks/"):
                r = service.task_detail(store, auth, u.path.rsplit("/", 1)[1]); return self._send(200 if r["ok"] else 404, r)
            if u.path.startswith("/v0/artifacts/"):
                r = service.artifact_body(store, auth, u.path.rsplit("/", 1)[1]); return self._send(200 if r["ok"] else 404, r)
            self._send(404, {"ok": False, "error": {"code": "not_found", "message": u.path}})
        def do_POST(self):
            auth = self._auth()
            if not auth: return
            if urlparse(self.path).path != "/v0/commands":
                return self._send(404, {"ok": False, "error": {"code": "not_found", "message": self.path}})
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if n > 100_000: raise ValueError
                cmd = json.loads(self.rfile.read(n))
            except (ValueError, json.JSONDecodeError):
                return self._send(400, {"ok": False, "error": {"code": "invalid_command", "message": "body must be a JSON command"}})
            r = service.handle(store, cmd, auth)
            self._send(200 if r["ok"] else 409 if r["error"]["code"] in ("stale_version", "approval_stale", "invalid_transition") else 400, r)
    return H

def serve(store: Store, port: int, origin: str, token: str | None = None) -> int:
    token = token or secrets.token_urlsafe(24)
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(store, token, origin))
    print(f"offices API on http://127.0.0.1:{srv.server_port}  (store: {'REHEARSAL' if store.simulation else 'live'})")
    print(f"allowed origin: {origin}\nbearer token (shown once, not stored): {token}")
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    return 0
