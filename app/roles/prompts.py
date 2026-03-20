from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.roles.catalog import ROLE_SPECS
from app.roles.models import RoleSpec, WorkflowRole


@dataclass(frozen=True)
class RolePromptSpec:
    prompt_id: str
    role_id: WorkflowRole
    path: Path
    title: str
    summary: str

    def load_text(self) -> str:
        return self.path.read_text(encoding="utf-8").strip()

    def to_metadata_record(self) -> dict[str, str]:
        return {
            "prompt_id": self.prompt_id,
            "role_id": self.role_id.value,
            "title": self.title,
            "summary": self.summary,
            "path": str(self.path),
        }


class RolePromptRegistry:
    def __init__(self, prompt_specs: tuple[RolePromptSpec, ...]) -> None:
        self._prompt_specs = {spec.prompt_id: spec for spec in prompt_specs}
        self._by_role = {spec.role_id: spec for spec in prompt_specs}

    def get_by_prompt_id(self, prompt_id: str) -> RolePromptSpec | None:
        return self._prompt_specs.get(prompt_id)

    def get_for_role(self, role: WorkflowRole | str) -> RolePromptSpec | None:
        try:
            workflow_role = role if isinstance(role, WorkflowRole) else WorkflowRole(role)
        except ValueError:
            return None
        return self._by_role.get(workflow_role)

    def require_for_role(self, role: WorkflowRole | str) -> RolePromptSpec:
        prompt = self.get_for_role(role)
        if prompt is None:
            role_name = role.value if isinstance(role, WorkflowRole) else role
            raise KeyError(f"No canonical role prompt registered for: {role_name}")
        return prompt

    def list_prompts(self) -> list[RolePromptSpec]:
        return list(self._prompt_specs.values())


_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts" / "roles"

ROLE_PROMPT_SPECS: tuple[RolePromptSpec, ...] = tuple(
    RolePromptSpec(
        prompt_id=spec.canonical_prompt_id or spec.role_name,
        role_id=spec.role_id,
        path=_PROMPT_DIR / f"{spec.role_name}.md",
        title=f"{spec.role_name.replace('_', ' ').title()} Role Prompt",
        summary=spec.mission,
    )
    for spec in ROLE_SPECS
)

ROLE_PROMPT_REGISTRY = RolePromptRegistry(ROLE_PROMPT_SPECS)


def role_prompt_for_spec(role_spec: RoleSpec) -> RolePromptSpec:
    return ROLE_PROMPT_REGISTRY.require_for_role(role_spec.role_id)
