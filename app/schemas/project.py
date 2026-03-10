from datetime import datetime, timezone
from dataclasses import dataclass, field


@dataclass
class Project:
    project_id: str
    name: str
    description: str
    status: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))