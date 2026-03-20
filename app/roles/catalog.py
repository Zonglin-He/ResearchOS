from __future__ import annotations

from app.roles.models import AgentRoleBinding, RoleArtifactContract, WorkflowRole


ROLE_ARTIFACT_CONTRACTS: dict[str, tuple[RoleArtifactContract, ...]] = {
    WorkflowRole.LIBRARIAN.value: (
        RoleArtifactContract(
            role_name=WorkflowRole.LIBRARIAN.value,
            artifact_type="paper_card",
            description="Structured retrieval summary for a paper or source.",
        ),
    ),
    WorkflowRole.SYNTHESIZER.value: (
        RoleArtifactContract(
            role_name=WorkflowRole.SYNTHESIZER.value,
            artifact_type="gap_map",
            description="Clustered research gaps and candidate directions.",
        ),
    ),
    WorkflowRole.HYPOTHESIST.value: (
        RoleArtifactContract(
            role_name=WorkflowRole.HYPOTHESIST.value,
            artifact_type="hypothesis_set",
            description="Explicit hypotheses and proposed research directions.",
        ),
    ),
    WorkflowRole.EXPERIMENT_DESIGNER.value: (
        RoleArtifactContract(
            role_name=WorkflowRole.EXPERIMENT_DESIGNER.value,
            artifact_type="experiment_spec",
            description="Experiment plan, baselines, metrics, and budget assumptions.",
        ),
    ),
    WorkflowRole.EXECUTOR.value: (
        RoleArtifactContract(
            role_name=WorkflowRole.EXECUTOR.value,
            artifact_type="run_manifest",
            description="Execution record with metrics and explicit produced artifacts.",
        ),
    ),
    WorkflowRole.ANALYST.value: (
        RoleArtifactContract(
            role_name=WorkflowRole.ANALYST.value,
            artifact_type="result_summary",
            description="Structured analysis of run outcomes and anomalies.",
        ),
    ),
    WorkflowRole.REVIEWER.value: (
        RoleArtifactContract(
            role_name=WorkflowRole.REVIEWER.value,
            artifact_type="review_report",
            description="Quality review report covering blocking issues and decision.",
        ),
    ),
    WorkflowRole.VERIFIER.value: (
        RoleArtifactContract(
            role_name=WorkflowRole.VERIFIER.value,
            artifact_type="verification_report",
            description="Evidence-chain and methodological verification report.",
        ),
    ),
    WorkflowRole.PUBLISHER.value: (
        RoleArtifactContract(
            role_name=WorkflowRole.PUBLISHER.value,
            artifact_type="paper_draft",
            description="Draft section or paper content aligned with frozen evidence.",
        ),
    ),
    WorkflowRole.ARCHIVIST.value: (
        RoleArtifactContract(
            role_name=WorkflowRole.ARCHIVIST.value,
            artifact_type="archive_entry",
            description="Registry curation note with lesson/provenance linkage.",
        ),
    ),
}


def reader_role_binding() -> AgentRoleBinding:
    return AgentRoleBinding(
        agent_name="reader_agent",
        default_role=WorkflowRole.LIBRARIAN,
        secondary_roles=(WorkflowRole.SCOPER,),
        task_kind_roles={
            "paper_ingest": WorkflowRole.LIBRARIAN,
            "repo_ingest": WorkflowRole.LIBRARIAN,
            "read_source": WorkflowRole.SCOPER,
        },
        artifact_contracts=ROLE_ARTIFACT_CONTRACTS,
    )


def mapper_role_binding() -> AgentRoleBinding:
    return AgentRoleBinding(
        agent_name="mapper_agent",
        default_role=WorkflowRole.SYNTHESIZER,
        artifact_contracts=ROLE_ARTIFACT_CONTRACTS,
    )


def builder_role_binding() -> AgentRoleBinding:
    return AgentRoleBinding(
        agent_name="builder_agent",
        default_role=WorkflowRole.EXPERIMENT_DESIGNER,
        secondary_roles=(WorkflowRole.HYPOTHESIST, WorkflowRole.EXECUTOR),
        task_kind_roles={
            "build_spec": WorkflowRole.EXPERIMENT_DESIGNER,
            "implement_experiment": WorkflowRole.EXECUTOR,
            "reproduce_baseline": WorkflowRole.EXECUTOR,
        },
        artifact_contracts=ROLE_ARTIFACT_CONTRACTS,
    )


def reviewer_role_binding() -> AgentRoleBinding:
    return AgentRoleBinding(
        agent_name="reviewer_agent",
        default_role=WorkflowRole.REVIEWER,
        artifact_contracts=ROLE_ARTIFACT_CONTRACTS,
    )


def writer_role_binding() -> AgentRoleBinding:
    return AgentRoleBinding(
        agent_name="writer_agent",
        default_role=WorkflowRole.PUBLISHER,
        artifact_contracts=ROLE_ARTIFACT_CONTRACTS,
    )


def style_role_binding() -> AgentRoleBinding:
    return AgentRoleBinding(
        agent_name="style_agent",
        default_role=WorkflowRole.PUBLISHER,
        artifact_contracts=ROLE_ARTIFACT_CONTRACTS,
    )


def analyst_role_binding() -> AgentRoleBinding:
    return AgentRoleBinding(
        agent_name="analyst_agent",
        default_role=WorkflowRole.ANALYST,
        artifact_contracts=ROLE_ARTIFACT_CONTRACTS,
    )


def verifier_role_binding() -> AgentRoleBinding:
    return AgentRoleBinding(
        agent_name="verifier_agent",
        default_role=WorkflowRole.VERIFIER,
        artifact_contracts=ROLE_ARTIFACT_CONTRACTS,
    )


def archivist_role_binding() -> AgentRoleBinding:
    return AgentRoleBinding(
        agent_name="archivist_agent",
        default_role=WorkflowRole.ARCHIVIST,
        artifact_contracts=ROLE_ARTIFACT_CONTRACTS,
    )

