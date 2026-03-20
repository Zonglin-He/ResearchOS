from dataclasses import dataclass, field
from typing import Any


@dataclass
class ArtifactRecord:
    artifact_id: str
    run_id: str
    kind: str
    path: str
    hash: str
    metadata: dict[str, Any] = field(default_factory=dict)
