from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


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
class AgentRoleBinding:
    agent_name: str
    default_role: WorkflowRole
    secondary_roles: tuple[WorkflowRole, ...] = ()
    task_kind_roles: dict[str, WorkflowRole] = field(default_factory=dict)
    artifact_contracts: dict[str, tuple[RoleArtifactContract, ...]] = field(default_factory=dict)

    def resolve_role(self, task_kind: str) -> WorkflowRole:
        return self.task_kind_roles.get(task_kind, self.default_role)

    def expected_artifact_types(self, task_kind: str) -> list[str]:
        role = self.resolve_role(task_kind)
        contracts = self.artifact_contracts.get(role.value, ())
        return [contract.artifact_type for contract in contracts]

