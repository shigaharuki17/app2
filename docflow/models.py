from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class Message:
    sender: str
    receiver: str
    kind: str
    payload: dict[str, Any]
    timestamp: str = field(default_factory=now)


@dataclass
class AgentResult:
    output: dict[str, Any]
    messages: list[Message] = field(default_factory=list)


@dataclass
class WorkflowState:
    id: str
    filename: str
    source: str
    mode: str = "offline"
    status: str = "pending"
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    nodes: dict[str, str] = field(default_factory=lambda: {
        "analyzer": "pending", "writer": "pending", "reviewer": "pending"
    })
    outputs: dict[str, Any] = field(default_factory=dict)
    messages: list[dict[str, Any]] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)
    attempts: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowState":
        return cls(**data)
