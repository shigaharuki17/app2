import json
import re
import threading
from pathlib import Path
from .models import WorkflowState, now


class StateStore:
    """Atomic JSON checkpoints. Each run has exactly one orchestrator worker."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def path(self, run_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise ValueError("无效的任务 ID")
        return self.root / f"{run_id}.json"

    def save(self, state: WorkflowState) -> None:
        with self.lock:
            state.updated_at = now()
            target = self.path(state.id)
            temp = target.with_suffix(".tmp")
            temp.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(target)

    def load(self, run_id: str) -> WorkflowState:
        with self.lock:
            return WorkflowState.from_dict(json.loads(self.path(run_id).read_text(encoding="utf-8")))

    def list(self) -> list[dict]:
        with self.lock:
            items = []
            for path in self.root.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    items.append({k: data[k] for k in (
                        "id", "filename", "mode", "status", "created_at", "updated_at"
                    )})
                except (ValueError, KeyError):
                    continue
            return sorted(items, key=lambda x: x["created_at"], reverse=True)

    def recover_interrupted(self) -> int:
        count = 0
        for item in self.list():
            state = self.load(item["id"])
            if state.status in ("running", "pending"):
                state.status = "failed"
                state.error = "上次运行被中断，可点击恢复；已完成的节点会保留。"
                for name, status in state.nodes.items():
                    if status == "running":
                        state.nodes[name] = "failed"
                self.save(state)
                count += 1
        return count
