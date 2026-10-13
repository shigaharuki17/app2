from dataclasses import asdict
from uuid import uuid4
from .agents import AnalyzerAgent, WriterAgent, ReviewerAgent
from .models import WorkflowState, now


class WorkflowEngine:
    """Sequential workflow, persisted state, conditional review/revision loop."""

    def __init__(self, store, agents=None, max_revisions=1):
        self.store = store
        self.agents = agents or [AnalyzerAgent(), WriterAgent(), ReviewerAgent()]
        self.max_revisions = max_revisions

    def create(self, filename, source, mode="offline"):
        if mode not in ("offline", "ai"):
            raise ValueError("模式必须为 offline 或 ai")
        if not source.strip():
            raise ValueError("请输入 Python 源码")
        if len(source.encode("utf-8")) > 256 * 1024:
            raise ValueError("源码不能超过 256 KB")
        state = WorkflowState(uuid4().hex, filename, source, mode,
                              nodes={agent.name: "pending" for agent in self.agents})
        self.store.save(state)
        return state

    def log(self, state, event, agent=None, detail=""):
        state.logs.append({"time": now(), "event": event, "agent": agent, "detail": detail})
        self.store.save(state)

    def execute_node(self, state, agent):
        state.nodes[agent.name] = "running"
        state.attempts[agent.name] = state.attempts.get(agent.name, 0) + 1
        self.log(state, "node_started", agent.name, f"第 {state.attempts[agent.name]} 次执行")
        try:
            result = agent.run(state)
            state.outputs[agent.name] = result.output
            state.messages.extend(asdict(m) for m in result.messages)
            state.nodes[agent.name] = "succeeded"
            self.log(state, "node_completed", agent.name, f"发送 {len(result.messages)} 条消息")
        except Exception as exc:
            state.nodes[agent.name] = "failed"
            state.status = "failed"
            state.error = str(exc)[:500]
            self.log(state, "node_failed", agent.name, state.error)
            raise

    def run(self, state):
        state.status = "running"
        state.error = None
        self.log(state, "workflow_started")
        try:
            for agent in self.agents:
                if state.nodes[agent.name] != "succeeded":
                    self.execute_node(state, agent)
                else:
                    self.log(state, "checkpoint_reused", agent.name, "复用已完成节点")
            reviewer = next((a for a in self.agents if a.name == "reviewer"), None)
            writer = next((a for a in self.agents if a.name == "writer"), None)
            # Total automatic revisions per run is bounded, even after resume.
            while reviewer and writer and not state.outputs["reviewer"]["approved"]:
                if state.attempts.get("writer", 0) >= self.max_revisions + 1:
                    state.status = "rejected"
                    state.error = "审校未通过，已达到修订上限；请查看问题列表。"
                    self.log(state, "workflow_rejected", detail=state.error)
                    return state
                self.log(state, "revision_requested", "reviewer", "审校未通过，返回文档 Agent")
                # Invalidate the previous review before a new draft is persisted.
                # A restart must never reuse the review of an older draft.
                state.nodes["writer"] = "pending"
                state.nodes["reviewer"] = "pending"
                self.store.save(state)
                self.execute_node(state, writer)
                self.execute_node(state, reviewer)
            state.status = "completed"
            self.log(state, "workflow_completed")
        except Exception:
            # Error state was already checkpointed; caller receives a failed run.
            pass
        return state

    def resume(self, run_id):
        state = self.store.load(run_id)
        if state.status != "failed":
            raise ValueError("仅失败或中断的任务可以恢复")
        return self.run(state)
