import json, shutil, tempfile, threading, unittest, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from offices import api
from offices.store import Store

class TestApi(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(); self.st = Store(self.dir)
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), api.make_handler(self.st, "tok", "http://localhost:8080"))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_port}"
    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close(); self.st.db.close(); shutil.rmtree(self.dir)
    def call(self, path, token="tok", body=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body else None,
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    def test_token_required_and_manager_can_create_but_not_run(self):
        self.assertEqual(self.call("/v0/snapshot", token="wrong")[0], 401)
        cmd = {"command_id": "cmd_api_00001", "idempotency_key": "api-key-00001", "actor": {"id": "someone-else"},
               "scope": {"office": "okfilm"}, "action": "task.create", "params": {"title": "API işi", "workflow": "okfilm.production_plan", "queue": True}}
        code, r = self.call("/v0/commands", body=cmd)
        self.assertEqual(code, 200); self.assertTrue(r["ok"])
        code, snap = self.call("/v0/snapshot")
        self.assertEqual(snap["tasks"][0]["state"], "queued")      # the API never starts a run
        self.assertEqual(snap["runs"], [])
        code, ev = self.call("/v0/events?since=0")
        self.assertEqual([e["type"] for e in ev["events"]], ["task.created", "task.queued"])
        self.assertEqual(ev["events"][0]["payload"]["by"], "owner")  # authority comes from the token, not the body
        self.assertEqual(self.call("/v0/run")[0], 404)

if __name__ == "__main__":
    unittest.main()
