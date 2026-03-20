from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageBoundary:
    database_backend: str
    database_location: str
    registry_dir: str
    artifacts_dir: str
    freezes_dir: str
    state_dir: str


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path

    @classmethod
    def from_root(cls, root: str | Path) -> "WorkspacePaths":
        return cls(Path(root).expanduser().resolve())

    @property
    def registry_dir(self) -> Path:
        return self.root / "registry"

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "artifacts"

    @property
    def freezes_dir(self) -> Path:
        return self.registry_dir / "freezes"

    @property
    def experiments_dir(self) -> Path:
        return self.registry_dir / "experiments"

    @property
    def state_dir(self) -> Path:
        return self.root / "state"

    @property
    def provider_health_state_file(self) -> Path:
        return self.state_dir / "provider_health.yaml"

    def registry_file(self, name: str) -> Path:
        return self.registry_dir / name

    def storage_boundary(
        self,
        *,
        database_backend: str,
        database_location: str,
    ) -> StorageBoundary:
        return StorageBoundary(
            database_backend=database_backend,
            database_location=database_location,
            registry_dir=str(self.registry_dir),
            artifacts_dir=str(self.artifacts_dir),
            freezes_dir=str(self.freezes_dir),
            state_dir=str(self.state_dir),
        )
