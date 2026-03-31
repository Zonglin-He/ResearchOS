from dataclasses import dataclass, field
from typing import Any, Literal

from app.routing.models import ResolvedDispatch
from app.schemas.strategy import HandoffPacket
from app.schemas.task import Task

AgentResultStatus = Literal["success",
"fail",
"handoff",
"needs_approval",]

@dataclass
class AgentResult:
    status: AgentResultStatus
    output: dict[str, Any] = field(default_factory= dict)
    artifacts: list[str] = field(default_factory=list)
    next_tasks: list[Task] = field(default_factory=list)
    audit_notes: list[str] = field(default_factory=list)
    routing: ResolvedDispatch | None = None
    handoff_packet: HandoffPacket | None = None
    evidence_used: list[str] = field(default_factory=list)
