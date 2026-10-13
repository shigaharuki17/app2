import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from docflow.agents import AnalyzerAgent, WriterAgent, ReviewerAgent, function_info
from docflow.models import AgentResult, WorkflowState
from docflow.store import StateStore
from docflow.workflow import WorkflowEngine

SOURCE = '''"""示例模块。"""
class Greeter:
    """欢迎服务。"""
    async def greet(self, name: str = "world") -> str:
        """返回问候语。"""
        if not name:
            raise ValueError("empty")
        return "Hello " + name

def total(*values: int, scale: int = 1) -> int:
    return sum(values) * scale
'''


class BrokenFirstWriter(WriterAgent):
    def run(self, state):
        if state.attempts[self.name] == 1:
            return AgentResult({"document": "# incomplete"})
        return super().run(state)


class AlwaysBrokenWriter(WriterAgent):
    def run(self, state):
        return AgentResult({"document": "# incomplete"})


class FailsOnceWriter(WriterAgent):
    def run(self, state):
        if state.attempts[self.name] == 1:
            raise RuntimeError("temporary service failure")
        return super().run(state)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = StateStore(Path(self.temp.name))
        self.engine = WorkflowEngine(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_flow_and_message_chain(self):
        state = self.engine.run(self.engine.create("demo.py", SOURCE))
        self.assertEqual(state.status, "completed")
        self.assertTrue(state.outputs["reviewer"]["approved"])
        self.assertEqual(state.outputs["reviewer"]["coverage"], {"covered": 2, "total": 2})
        self.assertEqual([(m["sender"], m["receiver"]) for m in state.messages],
                         [("analyzer", "writer"), ("writer", "reviewer"), ("reviewer", "orchestrator")])
        self.assertEqual(self.store.load(state.id).status, "completed")

    def test_ast_signatures_async_and_defaults(self):
        state = self.engine.run(self.engine.create("demo.py", SOURCE))
        facts = state.outputs["analyzer"]
        self.assertIn("scale: int=1", facts["functions"][0]["signature"])
        method = facts["classes"][0]["methods"][0]
        self.assertTrue(method["async"])
        self.assertEqual(method["raises"], ["ValueError('empty')"])

    def test_syntax_error_fails_without_running_writer(self):
        state = self.engine.run(self.engine.create("bad.py", "def broken(:"))
        self.assertEqual(state.status, "failed")
        self.assertEqual(state.nodes["writer"], "pending")
        self.assertIn("语法错误", state.error)

    def test_source_is_never_executed(self):
        marker = Path(self.temp.name) / "executed"
        source = f"from pathlib import Path\nPath({str(marker)!r}).write_text('BAD')"
        self.engine.run(self.engine.create("dangerous.py", source))
        self.assertFalse(marker.exists())

    def test_review_revision_branch(self):
        engine = WorkflowEngine(self.store, [AnalyzerAgent(), BrokenFirstWriter(), ReviewerAgent()])
        state = engine.run(engine.create("demo.py", SOURCE))
        self.assertEqual(state.status, "completed")
        self.assertEqual(state.attempts["writer"], 2)
        self.assertEqual(state.attempts["analyzer"], 1)
        self.assertTrue(any(m["kind"] == "revision_requested" for m in state.messages))

    def test_revision_limit(self):
        engine = WorkflowEngine(self.store, [AnalyzerAgent(), AlwaysBrokenWriter(), ReviewerAgent()])
        state = engine.run(engine.create("demo.py", SOURCE))
        self.assertEqual(state.status, "rejected")
        self.assertEqual(state.attempts["writer"], 2)

    def test_resume_during_revision_never_reuses_old_review(self):
        class InterruptedRevisionWriter(WriterAgent):
            def run(self, state):
                attempt = state.attempts[self.name]
                if attempt == 1:
                    return AgentResult({"document": "# incomplete"})
                if attempt == 2:
                    raise RuntimeError("interrupted revision")
                return super().run(state)
        engine = WorkflowEngine(self.store, [AnalyzerAgent(), InterruptedRevisionWriter(), ReviewerAgent()])
        state = engine.run(engine.create("demo.py", SOURCE))
        self.assertEqual(state.status, "failed")
        self.assertEqual(state.nodes["reviewer"], "pending")
        state = engine.resume(state.id)
        self.assertEqual(state.status, "completed")
        self.assertEqual(state.attempts["reviewer"], 2)
        self.assertTrue(state.outputs["reviewer"]["approved"])

    def test_resume_preserves_successful_checkpoint(self):
        engine = WorkflowEngine(self.store, [AnalyzerAgent(), FailsOnceWriter(), ReviewerAgent()])
        state = engine.run(engine.create("demo.py", SOURCE))
        self.assertEqual(state.status, "failed")
        recovered = engine.resume(state.id)
        self.assertEqual(recovered.status, "completed")
        self.assertEqual(recovered.attempts["analyzer"], 1)
        self.assertEqual(recovered.attempts["writer"], 2)

    def test_restart_marks_interrupted_runs(self):
        state = self.engine.create("demo.py", SOURCE)
        state.status = "running"
        state.nodes["analyzer"] = "running"
        self.store.save(state)
        self.assertEqual(self.store.recover_interrupted(), 1)
        self.assertEqual(self.store.load(state.id).nodes["analyzer"], "failed")
        self.assertEqual(self.engine.resume(state.id).status, "completed")

    def test_input_validation_and_path_traversal(self):
        for source in ("", "a" * (256 * 1024 + 1)):
            with self.assertRaises(ValueError):
                self.engine.create("demo.py", source)
        with self.assertRaises(ValueError):
            self.store.load("../../secrets")
        with self.assertRaises(ValueError):
            self.engine.create("demo.py", SOURCE, "invalid")

    def test_extension_uses_common_agent_interface(self):
        class SummaryAgent:
            name = "summary"
            def run(self, state):
                return AgentResult({"line_count": state.outputs["analyzer"]["line_count"]})
        engine = WorkflowEngine(self.store, [AnalyzerAgent(), SummaryAgent()])
        state = engine.run(engine.create("demo.py", SOURCE))
        self.assertEqual(state.status, "completed")
        self.assertEqual(state.nodes, {"analyzer": "succeeded", "summary": "succeeded"})

    def test_mock_deepseek_writer_and_semantic_review(self):
        def completion(system, data, **kwargs):
            value = ({"approved": True, "issues": [], "warnings": []}
                     if kwargs.get("json_output") else data["template"])
            return value, {"provider": "DeepSeek", "model": "mock", "usage": {"total_tokens": 10}}
        with patch("docflow.agents.complete", side_effect=completion) as mock:
            state = self.engine.run(self.engine.create("demo.py", SOURCE, "ai"))
        self.assertEqual(state.status, "completed")
        self.assertEqual(mock.call_count, 2)
        self.assertTrue(state.outputs["reviewer"]["semantic_review"]["approved"])

    def test_semantic_rejection_triggers_writer_revision(self):
        reviews = 0
        def completion(system, data, **kwargs):
            nonlocal reviews
            if kwargs.get("json_output"):
                reviews += 1
                value = {"approved": reviews > 1, "issues": ["补充异常说明"] if reviews == 1 else [], "warnings": []}
            else:
                value = data["template"]
            return value, {"provider": "mock"}
        with patch("docflow.agents.complete", side_effect=completion):
            state = self.engine.run(self.engine.create("demo.py", SOURCE, "ai"))
        self.assertEqual(state.status, "completed")
        self.assertEqual(state.attempts["writer"], 2)

    def test_bad_semantic_payload_is_failure(self):
        def completion(system, data, **kwargs):
            return ({} if kwargs.get("json_output") else data["template"]), {}
        with patch("docflow.agents.complete", side_effect=completion):
            state = self.engine.run(self.engine.create("demo.py", SOURCE, "ai"))
        self.assertEqual(state.status, "failed")
        self.assertEqual(state.nodes["reviewer"], "failed")


if __name__ == "__main__":
    unittest.main()
