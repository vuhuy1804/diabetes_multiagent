"""Agent message format inspired by §6.1–6.3 of the PDF.

Use when implementing agents in later phases. This class contains no business logic.
"""
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

AgentStatus = Literal["ok", "error", "skipped"]


@dataclass
class AgentMessage:
    request_id: str
    agent: str
    status: AgentStatus
    payload: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    version: str = "v0"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
