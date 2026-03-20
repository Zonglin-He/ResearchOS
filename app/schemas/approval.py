from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Approval:
    approval_id: str
    project_id: str
    target_type: str
    target_id: str
    approved_by: str
    decision: str
    comment: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
