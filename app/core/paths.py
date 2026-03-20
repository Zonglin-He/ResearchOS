from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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

    def registry_file(self, name: str) -> Path:
        return self.registry_dir / name
