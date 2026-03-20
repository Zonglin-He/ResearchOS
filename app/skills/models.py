from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.roles.models import WorkflowRole


@dataclass(frozen=True)
class ProviderWrapperSpec:
    provider: str
    relative_path: str
    wrapper_kind: str

    def to_record(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "relative_path": self.relative_path,
            "wrapper_kind": self.wrapper_kind,
        }


@dataclass(frozen=True)
class SkillSpec:
    name: str
    role_id: WorkflowRole
    description: str
    when_to_use: tuple[str, ...]
    when_not_to_use: tuple[str, ...]
    expected_inputs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    procedure_steps: tuple[str, ...]
    validation_checklist: tuple[str, ...]
    safety_notes: tuple[str, ...]
    path: Path
    references: tuple[str, ...] = ()
    provider_wrappers: tuple[ProviderWrapperSpec, ...] = ()
    tags: tuple[str, ...] = ()

    def to_metadata_record(self) -> dict[str, object]:
        return {
            "name": self.name,
            "role_id": self.role_id.value,
            "description": self.description,
            "when_to_use": list(self.when_to_use),
            "when_not_to_use": list(self.when_not_to_use),
            "expected_inputs": list(self.expected_inputs),
            "expected_outputs": list(self.expected_outputs),
            "references": list(self.references),
            "tags": list(self.tags),
            "path": str(self.path),
            "provider_wrappers": [wrapper.to_record() for wrapper in self.provider_wrappers],
        }


class RoleSkillRegistry:
    def __init__(self, skill_specs: tuple[SkillSpec, ...]) -> None:
        self._skill_specs = {spec.name: spec for spec in skill_specs}
        self._by_role: dict[WorkflowRole, list[SkillSpec]] = {}
        for spec in skill_specs:
            self._by_role.setdefault(spec.role_id, []).append(spec)

    def get(self, name: str) -> SkillSpec | None:
        return self._skill_specs.get(name)

    def require(self, name: str) -> SkillSpec:
        spec = self.get(name)
        if spec is None:
            raise KeyError(f"Unknown role skill: {name}")
        return spec

    def list_for_role(self, role: WorkflowRole | str) -> list[SkillSpec]:
        try:
            workflow_role = role if isinstance(role, WorkflowRole) else WorkflowRole(role)
        except ValueError:
            return []
        return list(self._by_role.get(workflow_role, ()))

    def load_instructions(self, name: str) -> str:
        return self.require(name).path.read_text(encoding="utf-8").strip()

    def list_all(self) -> list[SkillSpec]:
        return list(self._skill_specs.values())
