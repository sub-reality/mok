import json, shutil, tempfile, unittest, uuid
from pathlib import Path
from offices import service, executor, providers, contract
from offices.profiles import owner, agent_ctx
from offices.providers import RunResult
from offices.store import Store

SAMPLES = Path(__file__).resolve().parents[1] / "samples"

def cmd(office, action, params, expected=None, key=None):
    c = {"command_id": "cmd_" + uuid.uuid4().hex[:12], "idempotency_key": key or "k_" + uuid.uuid4().hex,
         "actor": {"id": "owner"}, "scope": {"office": office}, "action": action, "params": params}
    if expected is not None:
        c["expected_version"] = expected
    return c

class Base(unittest.TestCase):
    sim = False
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.st = Store(self.dir, simulation=self.sim)
        shutil.copytree(SAMPLES / "okfilm" / "demo-brief", self.st.source_root("okfilm") / "demo-brief")
        shutil.copytree(SAMPLES / "institute" / "part-ix", self.st.source_root("institute") / "part-ix")
        shutil.copytree(SAMPLES / "school" / "decks", self.st.source_root("school") / "decks")
        self.o = owner()
    def tearDown(self):
        self.st.db.close(); shutil.rmtree(self.dir)
    def make(self, queue=True, **extra):
        p = {"title": "Tanıtım filmi planı", "workflow": "okfilm.production_plan", "source_packet": "demo-brief",
             "due": "2026-12-04", "queue": queue, "options": {"as_of": "2026-11-17"}, **extra}
        r = service.handle(self.st, cmd("okfilm", "task.create", p), self.o)
        self.assertTrue(r["ok"], r)
        return r["result"]["task_id"]

class TestContract(Base):
    def test_fixtures_and_events_validate(self):
        tid = self.make()
        executor.run_task(self.st, tid, providers.MockProvider())
        for e in service.events_since(self.st, self.o, 0)["events"]:
            self.assertEqual(contract.validate("event", e), [], e)
        self.assertEqual(contract.validate("snapshot", service.snapshot(self.st, self.o)), [])
        fx = Path(contract.contract_dir()) / "fixtures"
        for f in fx.glob("command.*.json"):
            self.assertEqual(contract.validate("command", json.loads(f.read_text())), [], f.name)
        for f in fx.glob("invalid.command.*.json"):
            self.assertNotEqual(contract.validate("command", json.loads(f.read_text())), [], f.name)

    def test_invalid_command_rejected(self):
        r = service.handle(self.st, {"action": "task.create"}, self.o)
        self.assertEqual(r["error"]["code"], "invalid_command")

    def test_duplicate_command_has_no_second_effect(self):
        c = cmd("okfilm", "task.create", {"title": "x", "workflow": "okfilm.production_plan"}, key="same-key-123")
        a = service.handle(self.st, c, self.o); b = service.handle(self.st, c, self.o)
        self.assertEqual(a["result"]["task_id"], b["result"]["task_id"]); self.assertTrue(b.get("duplicate"))
        self.assertEqual(len(service.snapshot(self.st, self.o)["tasks"]), 1)

    def test_stale_version_rejected_and_retryable(self):
        tid = self.make(queue=False)
        r = service.handle(self.st, cmd("okfilm", "task.queue", {"task_id": tid}, expected=7), self.o)
        self.assertEqual(r["error"]["code"], "stale_version")
        self.assertEqual(self.st.task(tid)["state"], "draft")
        self.assertTrue(service.handle(self.st, cmd("okfilm", "task.queue", {"task_id": tid}, expected=1), self.o)["ok"])

    def test_invalid_transition(self):
        tid = self.make(queue=False)
        r = service.handle(self.st, cmd("okfilm", "approval.decide", {"task_id": tid, "subject": "review", "decision": "accept",
                                                                     "artifact_sha256": "0" * 64}, expected=1), self.o)
        self.assertEqual(r["error"]["code"], "invalid_transition")

    def test_replay_and_cursor(self):
        tid = self.make()
        first = service.events_since(self.st, self.o, 0)
        again = service.events_since(self.st, self.o, 0)
        self.assertEqual(first, again)
        self.assertEqual(service.events_since(self.st, self.o, first["cursor"])["events"], [])
        self.assertEqual([e["cursor"] for e in first["events"]], sorted(e["cursor"] for e in first["events"]))
        self.st.q("DELETE FROM events WHERE cursor<=1")
        self.st.emit("task.queued", "okfilm", {}, task_id=tid); self.st.emit("task.queued", "okfilm", {}, task_id=tid)
        self.st.q("DELETE FROM events WHERE cursor<=2")
        self.assertEqual(service.events_since(self.st, self.o, 0)["error"]["code"], "cursor_expired")

class TestPermissions(Base):
    def test_cross_office_command_denied(self):
        a = agent_ctx("okfilm")
        r = service.handle(self.st, cmd("institute", "transfer.record", {"to_office": "okfilm"}), a)
        self.assertEqual(r["error"]["code"], "forbidden_office")
        r = service.handle(self.st, cmd("okfilm", "task.create", {"title": "x", "workflow": "okfilm.production_plan"}), a)
        self.assertEqual(r["error"]["code"], "forbidden_action")

    def test_client_scope_is_not_authority(self):
        tid = self.make(queue=False)
        r = service.handle(self.st, cmd("institute", "task.queue", {"task_id": tid}, expected=1), self.o)
        self.assertEqual(r["error"]["code"], "forbidden_office")
        r = service.handle(self.st, cmd("institute", "task.create", {"title": "x", "workflow": "okfilm.production_plan"}), self.o)
        self.assertEqual(r["error"]["code"], "workflow_office_mismatch")

    def test_agent_snapshot_is_scoped(self):
        self.make()
        self.assertEqual(service.snapshot(self.st, agent_ctx("school"))["tasks"], [])

    def test_toolbox_confines_paths_and_tools(self):
        class Nosy:
            name = "mock"
            def run(self, task, box, sp, up):
                self.r = [box.call("read_source", {"name": "../../institute/sources/part-ix/README.txt"}),
                          box.call("read_source", {"name": "/etc/passwd"}),
                          box.call("write_artifact", {"name": "../escape.md", "content": "x"}),
                          box.call("bash", {"command": "id"}),
                          box.call("record_evidence", {"kind": "quote", "locator": "brief.md:9999", "note": "invented"})]
                box.call("write_artifact", {"name": "ok.md", "content": "fine"})
                return RunResult("mock", None)
        n = Nosy(); tid = self.make()
        executor.run_task(self.st, tid, n)
        self.assertTrue(all(not ok for ok, _ in n.r), n.r)
        self.assertFalse((Path(self.dir) / "okfilm" / "artifacts" / "escape.md").exists())
        d = service.task_detail(self.st, self.o, tid)
        self.assertEqual(d["runs"][0]["tool_denials"], 5)

class TestRuns(Base):
    def test_mock_run_reaches_review_then_acceptance_is_separate(self):
        tid = self.make()
        res = executor.run_task(self.st, tid, providers.MockProvider())
        self.assertEqual(res["state"], "awaiting_review")
        types = [e["type"] for e in service.events_since(self.st, self.o, 0)["events"]]
        self.assertIn("run.completed", types); self.assertNotIn("task.accepted", types)
        body = service.artifact_body(self.st, self.o, res["artifact_id"])
        self.assertIn("No model inference", body["content"])
        t = self.st.task(tid)
        r = service.handle(self.st, cmd("okfilm", "approval.decide", {"task_id": tid, "subject": "review", "decision": "accept",
                                                                     "artifact_sha256": res["sha256"]}, expected=t["version"]), self.o)
        self.assertEqual(r["result"]["state"], "accepted")

    def test_changed_artifact_invalidates_approval(self):
        tid = self.make()
        res = executor.run_task(self.st, tid, providers.MockProvider())
        art = self.st.latest_artifact(tid)
        Path(art["path"]).write_text("tampered after review")
        r = service.handle(self.st, cmd("okfilm", "approval.decide", {"task_id": tid, "subject": "review", "decision": "accept",
                                                                     "artifact_sha256": res["sha256"]}, expected=self.st.task(tid)["version"]), self.o)
        self.assertEqual(r["error"]["code"], "approval_stale")
        self.assertEqual(self.st.task(tid)["state"], "awaiting_review")

    def test_revise_requeues(self):
        tid = self.make()
        res = executor.run_task(self.st, tid, providers.MockProvider())
        r = service.handle(self.st, cmd("okfilm", "approval.decide", {"task_id": tid, "subject": "review", "decision": "revise",
                           "artifact_sha256": res["sha256"], "note": "tarihleri düzelt"}, expected=self.st.task(tid)["version"]), self.o)
        self.assertEqual(r["result"]["state"], "queued")

    def test_failed_tool_and_no_artifact_fail_the_run(self):
        class Empty:
            name = "mock"
            def run(self, task, box, sp, up):
                box.call("read_source", {"name": "does-not-exist.md"}); return RunResult("mock", None)
        tid = self.make()
        res = executor.run_task(self.st, tid, Empty())
        self.assertEqual(res["state"], "failed"); self.assertIn("no_artifact", res["error"])
        self.assertTrue(service.handle(self.st, cmd("okfilm", "task.queue", {"task_id": tid}, expected=self.st.task(tid)["version"]), self.o)["ok"])

    def test_cancel_is_a_request_until_worker_acknowledges(self):
        st, o = self.st, self.o
        class Slow:
            name = "mock"
            def run(self, task, box, sp, up):
                box.call("list_sources", {})
                r = service.handle(st, cmd("okfilm", "task.cancel", {"task_id": task["task_id"]}, expected=st.task(task["task_id"])["version"]), o)
                self.mid = (r["result"]["state"], st.task(task["task_id"])["state"])
                box.call("read_source", {"name": "brief.md"})   # raises Cancelled at the tool boundary
                return RunResult("mock", None)
        s = Slow(); tid = self.make()
        res = executor.run_task(self.st, tid, s)
        self.assertEqual(s.mid, ("running", "running"))
        self.assertEqual(res["state"], "cancelled")
        ev = [e for e in service.events_since(self.st, self.o, 0)["events"] if e["type"].startswith("task.cancel")]
        self.assertEqual([e["type"] for e in ev], ["task.cancel_requested", "task.cancelled"])
        self.assertEqual(ev[1]["payload"]["acknowledged_by"], "worker")

    def test_budget_exhaustion_fails(self):
        class Loop:
            name = "mock"
            def run(self, task, box, sp, up):
                while True: box.call("list_sources", {})
        tid = self.make()
        self.assertEqual(executor.run_task(self.st, tid, Loop())["error"], "budget_exhausted")

    def test_model_substitution_is_a_failure_not_a_silent_success(self):
        class Sub:
            name = "claude"; model = "claude-fable-5-2"
            def run(self, task, box, sp, up):
                box.call("write_artifact", {"name": "a.md", "content": "x"})
                return RunResult("claude", self.model, "some-other-model", error="model_substituted: requested claude-fable-5-2, served some-other-model")
        tid = self.make()
        self.assertEqual(executor.run_task(self.st, tid, Sub())["state"], "failed")

class TestOkfilmRoles(Base):
    ROLES = {"okfilm.product_brief": "okfilm-product-manager", "okfilm.uix_spec": "okfilm-uix-designer", "okfilm.data_plan": "okfilm-data-engineer",
             "okfilm.edit_plan": "okfilm-editor", "okfilm.legal_review": "okfilm-lawyer", "okfilm.production_plan": "okfilm-worker"}
    def test_each_role_has_its_own_worker_brief_and_run(self):
        from offices import workflows
        for wf, agent in self.ROLES.items():
            tid = self.make(workflow=wf)
            res = executor.run_task(self.st, tid, providers.MockProvider())
            self.assertEqual(res["state"], "awaiting_review", wf)
            self.assertEqual(service.task_detail(self.st, self.o, tid)["runs"][0]["agent"], agent)
            self.assertIn("Not done", workflows.system_prompt(self.st.task(tid)))
        self.assertEqual({a["id"] for a in service.snapshot(self.st, self.o)["agents"] if a["office"] == "okfilm"}, set(self.ROLES.values()))
    def test_lawyer_brief_forbids_legal_advice_and_cannot_decide_approvals(self):
        from offices import workflows
        from offices.profiles import OFFICES
        tid = self.make(workflow="okfilm.legal_review")
        sp = workflows.system_prompt(self.st.task(tid))
        self.assertIn("NOT legal advice", sp); self.assertIn("Hukuki tavsiye değildir", sp)
        self.assertNotIn("date_math", OFFICES["okfilm"].workers["okfilm.uix_spec"].tools)
    def test_role_workflow_cannot_be_created_in_another_office(self):
        r = service.handle(self.st, cmd("institute", "task.create", {"title": "x", "workflow": "okfilm.legal_review"}), self.o)
        self.assertEqual(r["error"]["code"], "workflow_office_mismatch")

class TestLesson(Base):
    def test_one_prompt_at_a_time_hints_and_review(self):
        r = service.handle(self.st, cmd("school", "task.create", {"title": "Fokus 4 günlük cümle", "workflow": "school.lesson", "queue": True,
                           "options": {"deck": "fokus4-neue-arbeit.json", "mode": "socratic", "max_cards": 2}}), self.o)
        tid = r["result"]["task_id"]
        a = lambda p: service.handle(self.st, cmd("school", "lesson.attempt", {"task_id": tid, **p}), self.o)
        self.assertEqual(a({"card_id": "f4-2", "answer": "x"})["error"]["code"], "wrong_card")
        wrong = a({"card_id": "f4-1", "answer": "Ich habe Formulare"})["result"]
        self.assertFalse(wrong["correct"]); self.assertNotIn("correction", wrong)   # socratic: no answer handed over
        self.assertIn("haben + zu", a({"card_id": "f4-1", "hint": True})["result"]["hint"])
        ok = a({"card_id": "f4-1", "answer": "am ersten arbeitstag habe ich viele formulare auszufuellen"})["result"]
        self.assertTrue(ok["correct"]); self.assertEqual(ok["next"]["card_id"], "f4-2")
        a({"card_id": "f4-2", "answer": "Sie haben die Sicherheitsregeln im Studio zu beachten."})
        f = service.handle(self.st, cmd("school", "lesson.finish", {"task_id": tid}, expected=self.st.task(tid)["version"]), self.o)
        self.assertEqual(f["result"]["state"], "queued")
        res = executor.run_task(self.st, tid, providers.MockProvider())
        self.assertEqual(res["state"], "awaiting_review")
        # learner answers never reach the presentation read model
        self.assertNotIn("Formulare", json.dumps(service.snapshot(self.st, self.o)) + json.dumps(service.events_since(self.st, self.o, 0)))

class TestSimulationIsolation(Base):
    sim = True
    def test_rehearsal_store_is_flagged_and_refuses_live_provider(self):
        tid = self.make()
        with self.assertRaises(executor.NotRunnable):
            executor.run_task(self.st, tid, providers.ClaudeProvider())
        executor.run_task(self.st, tid, providers.MockProvider())
        self.assertTrue(all(e["simulation"] for e in service.events_since(self.st, self.o, 0)["events"]))
        self.st.db.close()
        with self.assertRaises(RuntimeError):
            Store(self.dir, simulation=False)
        self.st = Store(self.dir, simulation=True)

if __name__ == "__main__":
    unittest.main()
