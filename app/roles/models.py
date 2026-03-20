from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.routing.models import CapabilityClass


class WorkflowRole(str, Enum):
    SCOPER = "scoper"
    LIBRARIAN = "librarian"
    SYNTHESIZER = "synthesizer"
    HYPOTHESIST = "hypothesist"
    EXPERIMENT_DESIGNER = "experiment_designer"
    EXECUTOR = "executor"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    VERIFIER = "verifier"
    PUBLISHER = "publisher"
    ARCHIVIST = "archivist"


@dataclass(frozen=True)
class RoleArtifactContract:
    role_name: str
    artifact_type: str
    description: str


@dataclass(frozen=True)
class RoleProviderPreference:
    family_priority: tuple[str, ...] = ()
    model_priority: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class RoleSpec:
    role_id: WorkflowRole
    mission: str
    required_inputs: tuple[str, ...] = ()
    required_outputs: tuple[str, ...] = ()
    artifact_contracts: tuple[RoleArtifactContract, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
    review_checklist: tuple[str, ...] = ()
    default_capability_class: CapabilityClass = CapabilityClass.PLANNING
    default_provider_preference: RoleProviderPreference = field(default_factory=RoleProviderPreference)
    fallback_provider_preference: RoleProviderPreference = field(default_factory=RoleProviderPreference)

    @property
    def role_name(self) -> str:
        return self.role_id.value

    def expected_artifact_types(self) -> list[str]:
        return [contract.artifact_type for contract in self.artifact_contracts]

    def to_contract_record(self) -> dict[str, object]:
        return {
            "role_id": self.role_name,
            "mission": self.mission,
            "required_inputs": list(self.required_inputs),
            "required_outputs": list(self.required_outputs),
            "artifact_contracts": [
                {
                    "role_name": contract.role_name,
                    "artifact_type": contract.artifact_type,
                    "description": contract.description,
                }
                for contract in self.artifact_contracts
            ],
            "allowed_tools": list(self.allowed_tools),
            "forbidden_tools": list(self.forbidden_tools),
            "success_criteria": list(self.success_criteria),
            "review_checklist": list(self.review_checklist),
            "default_capability_class": self.default_capability_class.value,
            "default_provider_preference": {
                "family_priority": list(self.default_provider_preference.family_priority),
                "model_priority": {
                    family: list(models)
                    for family, models in self.default_provider_preference.model_priority.items()
                },
            },
            "fallback_provider_preference": {
                "family_priority": list(self.fallback_provider_preference.family_priority),
                "model_priority": {
                    family: list(models)
                    for family, models in self.fallback_provider_preference.model_priority.items()
                },
            },
        }


class RoleRegistry:
    def __init__(self, role_specs: tuple[RoleSpec, ...]) -> None:
        self._role_specs = {spec.role_id: spec for spec in role_specs}

    def get(self, role: WorkflowRole | str) -> RoleSpec | None:
        try:
            workflow_role = role if isinstance(role, WorkflowRole) else WorkflowRole(role)
        except ValueError:
            return None
        return self._role_specs.get(workflow_role)

    def require(self, role: WorkflowRole | str) -> RoleSpec:
        spec = self.get(role)
        if spec is None:
            role_name = role.value if isinstance(role, WorkflowRole) else role
            raise KeyError(f"Unknown workflow role: {role_name}")
        return spec

    def list_roles(self) -> list[RoleSpec]:
        return list(self._role_specs.values())


@dataclass(frozen=True)
class AgentRoleBinding:
    agent_name: str
    default_role: WorkflowRole
    secondary_roles: tuple[WorkflowRole, ...] = ()
    task_kind_roles: dict[str, WorkflowRole] = field(default_factory=dict)
    artifact_contracts: dict[str, tuple[RoleArtifactContract, ...]] = field(default_factory=dict)
    role_registry: RoleRegistry | None = None

    def resolve_role(self, task_kind: str) -> WorkflowRole:
        return self.task_kind_roles.get(task_kind, self.default_role)

    def expected_artifact_types(self, task_kind: str) -> list[str]:
        role_spec = self.resolve_role_spec(task_kind)
        if role_spec is not None:
            return role_spec.expected_artifact_types()
        role = self.resolve_role(task_kind)
        contracts = self.artifact_contracts.get(role.value, ())
        return [contract.artifact_type for contract in contracts]

    def resolve_role_spec(self, task_kind: str) -> RoleSpec | None:
        if self.role_registry is None:
            return None
        role = self.resolve_role(task_kind)
        return self.role_registry.get(role)

    def secondary_role_specs(self) -> tuple[RoleSpec, ...]:
        if self.role_registry is None:
            return ()
        return tuple(self.role_registry.require(role) for role in self.secondary_roles)
