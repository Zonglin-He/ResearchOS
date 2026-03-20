from dataclasses import dataclass, field
from typing import Any

from app.routing.models import ResolvedDispatch
from app.schemas.lesson import LessonRecord

@dataclass
class RunContext:
    run_id: str
    project_id: str
    task_id: str
    shared_state: dict[str, Any] = field(default_factory= dict)
    artifacts_dir: str= ""
    max_steps: int = 12
    routing: ResolvedDispatch | None = None
    prior_lessons: list[LessonRecord] = field(default_factory=list)
