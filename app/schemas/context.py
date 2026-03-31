from dataclasses import dataclass, field
from typing import Any, Callable

from app.routing.models import ResolvedDispatch
from app.schemas.lesson import LessonRecord
from app.schemas.strategy import StrategyTrace

@dataclass
class RunContext:
    run_id: str
    project_id: str
    task_id: str
    shared_state: dict[str, Any] = field(default_factory=dict)
    artifacts_dir: str = ""
    max_steps: int = 12
    routing: ResolvedDispatch | None = None
    prior_lessons: list[LessonRecord] = field(default_factory=list)
    checkpoint_dir: str = ""
    checkpoint_path: str | None = None
    resume_from_checkpoint: dict[str, Any] | None = None
    strategy_trace: StrategyTrace | None = None
    retrieval_evidence_ids: list[str] = field(default_factory=list)
    checkpoint_recorder: Callable[[str, dict[str, Any]], str | None] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def record_checkpoint(self, stage: str, payload: dict[str, Any]) -> str | None:
        if self.checkpoint_recorder is None:
            return None
        checkpoint_path = self.checkpoint_recorder(stage, payload)
        if checkpoint_path is not None:
            self.checkpoint_path = checkpoint_path
        return checkpoint_path
