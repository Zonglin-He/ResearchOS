from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.routing.models import ResolvedDispatch


@dataclass
class RunManifest:
    run_id: str
    spec_id: str
    git_commit: str
    config_hash: str
    dataset_snapshot: str
    seed: int
    gpu: str
    experiment_proposal_id: str | None = None
    experiment_branch: str | None = None
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    status: str = "pending"
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    dispatch_routing: ResolvedDispatch | None = None
