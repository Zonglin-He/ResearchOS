from datetime import datetime, timezone
from dataclasses import dataclass, field

from app.routing.models import DispatchProfile


@dataclass
class Project:
    project_id: str
    name: str
    description: str
    status: str
    dispatch_profile: DispatchProfile | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
