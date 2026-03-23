from __future__ import annotations

from app.roles.models import (
    AgentRoleBinding,
    RoleArtifactContract,
    RoleProviderPreference,
    RoleRegistry,
    RoleSpec,
    WorkflowRole,
)
from app.routing.models import (
    CapabilityClass,
    FallbackChain,
    InvocationBudgetPolicy,
    ProviderFamily,
    RoleRoutingPolicy,
)


def _artifact_contract(role: WorkflowRole, artifact_type: str, description: str) -> RoleArtifactContract:
    return RoleArtifactContract(
        role_name=role.value,
        artifact_type=artifact_type,
        description=description,
    )


def _prompt_id(role: WorkflowRole) -> str:
    return role.value


def _skill_name(role: WorkflowRole) -> str:
    return f"researchos-{role.value.replace('_', '-')}"


_REASONING_DEFAULT = RoleProviderPreference(
    family_priority=(
        ProviderFamily.CLAUDE.value,
        ProviderFamily.CODEX.value,
        ProviderFamily.GEMINI.value,
        ProviderFamily.LOCAL.value,
    ),
    model_priority={
        ProviderFamily.CLAUDE.value: ("sonnet",),
        ProviderFamily.CODEX.value: ("gpt-5.4",),
        ProviderFamily.GEMINI.value: ("gemini-3.1-pro-preview",),
        ProviderFamily.LOCAL.value: ("deterministic-reader",),
    },
)
_REASONING_FALLBACK = RoleProviderPreference(
    family_priority=(
        ProviderFamily.CODEX.value,
        ProviderFamily.GEMINI.value,
        ProviderFamily.LOCAL.value,
    ),
    model_priority={
        ProviderFamily.CODEX.value: ("gpt-5.4",),
        ProviderFamily.GEMINI.value: ("gemini-3.1-pro-preview",),
        ProviderFamily.LOCAL.value: ("deterministic-reader",),
    },
)
_RETRIEVAL_DEFAULT = RoleProviderPreference(
    family_priority=(
        ProviderFamily.GEMINI.value,
        ProviderFamily.CLAUDE.value,
        ProviderFamily.CODEX.value,
        ProviderFamily.LOCAL.value,
    ),
    model_priority={
        ProviderFamily.GEMINI.value: (
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite-preview",
        ),
        ProviderFamily.CLAUDE.value: ("sonnet",),
        ProviderFamily.CODEX.value: ("gpt-5.4",),
        ProviderFamily.LOCAL.value: ("deterministic-reader",),
    },
)
_SYNTHESIS_DEFAULT = RoleProviderPreference(
    family_priority=(
        ProviderFamily.GEMINI.value,
        ProviderFamily.CLAUDE.value,
        ProviderFamily.CODEX.value,
        ProviderFamily.LOCAL.value,
    ),
    model_priority={
        ProviderFamily.GEMINI.value: ("gemini-3.1-pro-preview", "gemini-3-flash-preview"),
        ProviderFamily.CLAUDE.value: ("sonnet",),
        ProviderFamily.CODEX.value: ("gpt-5.4",),
        ProviderFamily.LOCAL.value: ("deterministic-reader",),
    },
)
_EXECUTION_DEFAULT = RoleProviderPreference(
    family_priority=(
        ProviderFamily.CODEX.value,
        ProviderFamily.CLAUDE.value,
        ProviderFamily.LOCAL.value,
    ),
    model_priority={
        ProviderFamily.CODEX.value: ("gpt-5.3-codex", "gpt-5.4"),
        ProviderFamily.CLAUDE.value: ("sonnet",),
        ProviderFamily.LOCAL.value: ("deterministic-reader",),
    },
)
_ARCHIVAL_DEFAULT = RoleProviderPreference(
    family_priority=(
        ProviderFamily.GEMINI.value,
        ProviderFamily.LOCAL.value,
        ProviderFamily.CLAUDE.value,
        ProviderFamily.CODEX.value,
    ),
    model_priority={
        ProviderFamily.GEMINI.value: (
            "gemini-3.1-flash-lite-preview",
            "gemini-3-flash-preview",
        ),
        ProviderFamily.LOCAL.value: ("deterministic-reader",),
        ProviderFamily.CLAUDE.value: ("sonnet",),
        ProviderFamily.CODEX.value: ("gpt-5.4",),
    },
)


ROLE_SPECS: tuple[RoleSpec, ...] = (
    RoleSpec(
        role_id=WorkflowRole.SCOPER,
        mission="Define the research problem, sharpen scope, and decompose work into tractable questions.",
        required_inputs=("topic", "current_constraints", "source_context"),
        required_outputs=("research_question_tree", "scoping_notes"),
        allowed_tools=("filesystem", "paper_search", "pdf_parse"),
        forbidden_tools=("experiment_runner",),
        success_criteria=(
            "Research question is explicit and bounded.",
            "Subtasks are independently actionable.",
        ),
        review_checklist=(
            "State assumptions explicitly.",
            "Do not overclaim beyond provided evidence.",
        ),
        default_capability_class=CapabilityClass.PLANNING,
        default_provider_preference=_REASONING_DEFAULT,
        fallback_provider_preference=_REASONING_FALLBACK,
        canonical_prompt_id=_prompt_id(WorkflowRole.SCOPER),
        canonical_skill_names=(_skill_name(WorkflowRole.SCOPER),),
    ),
    RoleSpec(
        role_id=WorkflowRole.LIBRARIAN,
        mission="Retrieve, filter, and normalize sources into structured paper cards.",
        required_inputs=("source_material", "topic", "selection_criteria"),
        required_outputs=("paper_card",),
        artifact_contracts=(
            _artifact_contract(
                WorkflowRole.LIBRARIAN,
                "paper_card",
                "Structured retrieval summary for a paper or source.",
            ),
        ),
        allowed_tools=("paper_search", "pdf_parse", "filesystem"),
        forbidden_tools=("experiment_runner", "python_exec", "shell"),
        success_criteria=(
            "At least one source is captured as a structured paper card when evidence is available.",
            "Uncertainties and missing evidence remain explicit.",
        ),
        review_checklist=(
            "Preserve evidence references.",
            "Do not collapse unsupported details into confident claims.",
        ),
        default_capability_class=CapabilityClass.RETRIEVAL,
        default_provider_preference=_RETRIEVAL_DEFAULT,
        fallback_provider_preference=_REASONING_FALLBACK,
        canonical_prompt_id=_prompt_id(WorkflowRole.LIBRARIAN),
        canonical_skill_names=(_skill_name(WorkflowRole.LIBRARIAN),),
    ),
    RoleSpec(
        role_id=WorkflowRole.SYNTHESIZER,
        mission="Aggregate knowledge into gap maps, claim clusters, and candidate directions.",
        required_inputs=("paper_cards", "topic", "known_constraints"),
        required_outputs=("gap_map",),
        artifact_contracts=(
            _artifact_contract(
                WorkflowRole.SYNTHESIZER,
                "gap_map",
                "Clustered research gaps and candidate directions.",
            ),
        ),
        allowed_tools=("filesystem", "paper_search"),
        forbidden_tools=("experiment_runner",),
        success_criteria=(
            "Gap map groups related evidence cleanly.",
            "Novelty and difficulty are explicit where possible.",
        ),
        review_checklist=(
            "Separate observed gaps from speculative directions.",
            "Keep supporting papers attached to each gap when available.",
        ),
        default_capability_class=CapabilityClass.SYNTHESIS,
        default_provider_preference=_SYNTHESIS_DEFAULT,
        fallback_provider_preference=_REASONING_FALLBACK,
        canonical_prompt_id=_prompt_id(WorkflowRole.SYNTHESIZER),
        canonical_skill_names=(_skill_name(WorkflowRole.SYNTHESIZER),),
    ),
    RoleSpec(
        role_id=WorkflowRole.HYPOTHESIST,
        mission="Generate hypotheses and candidate research directions grounded in current evidence.",
        required_inputs=("gap_map", "paper_cards", "frozen_topic"),
        required_outputs=("hypothesis_set",),
        artifact_contracts=(
            _artifact_contract(
                WorkflowRole.HYPOTHESIST,
                "hypothesis_set",
                "Explicit hypotheses and proposed research directions.",
            ),
        ),
        allowed_tools=("filesystem", "paper_search"),
        forbidden_tools=("experiment_runner",),
        success_criteria=(
            "Hypotheses are falsifiable.",
            "Each proposed direction is grounded in current evidence.",
        ),
        review_checklist=(
            "State what would invalidate the hypothesis.",
            "Do not skip baseline alternatives.",
        ),
        default_capability_class=CapabilityClass.PLANNING,
        default_provider_preference=_REASONING_DEFAULT,
        fallback_provider_preference=_REASONING_FALLBACK,
        canonical_prompt_id=_prompt_id(WorkflowRole.HYPOTHESIST),
        canonical_skill_names=(_skill_name(WorkflowRole.HYPOTHESIST),),
    ),
    RoleSpec(
        role_id=WorkflowRole.EXPERIMENT_DESIGNER,
        mission="Turn research directions into executable experiment specs with explicit metrics and budget.",
        required_inputs=("hypothesis_set", "topic_freeze", "resource_constraints"),
        required_outputs=("experiment_spec",),
        artifact_contracts=(
            _artifact_contract(
                WorkflowRole.EXPERIMENT_DESIGNER,
                "experiment_spec",
                "Experiment plan, baselines, metrics, and budget assumptions.",
            ),
        ),
        allowed_tools=("filesystem", "git", "python_exec"),
        forbidden_tools=(),
        success_criteria=(
            "Spec names baselines, datasets, metrics, and failure criteria.",
            "Budget and execution assumptions are explicit.",
        ),
        review_checklist=(
            "Baseline comparisons are mandatory.",
            "Success and failure criteria are both present.",
        ),
        default_capability_class=CapabilityClass.PLANNING,
        default_provider_preference=_REASONING_DEFAULT,
        fallback_provider_preference=_REASONING_FALLBACK,
        canonical_prompt_id=_prompt_id(WorkflowRole.EXPERIMENT_DESIGNER),
        canonical_skill_names=(_skill_name(WorkflowRole.EXPERIMENT_DESIGNER),),
    ),
    RoleSpec(
        role_id=WorkflowRole.EXECUTOR,
        mission="Execute experiments, usually by reproducing or adapting a baseline implementation, and record run manifests and artifacts faithfully.",
        required_inputs=("experiment_spec", "code_state", "dataset_snapshot", "baseline_context"),
        required_outputs=("run_manifest",),
        artifact_contracts=(
            _artifact_contract(
                WorkflowRole.EXECUTOR,
                "run_manifest",
                "Execution record with metrics and explicit produced artifacts.",
            ),
        ),
        allowed_tools=("experiment_runner", "python_exec", "filesystem", "git", "shell"),
        forbidden_tools=(),
        success_criteria=(
            "Run manifest is complete and reproducible.",
            "Produced artifacts are explicitly registered.",
            "Baseline reuse versus novel modifications is explicit.",
        ),
        review_checklist=(
            "Record code/config provenance.",
            "Do not hide failed runs.",
        ),
        default_capability_class=CapabilityClass.EXECUTION,
        default_provider_preference=_EXECUTION_DEFAULT,
        fallback_provider_preference=RoleProviderPreference(
            family_priority=(ProviderFamily.CLAUDE.value, ProviderFamily.LOCAL.value),
            model_priority={
                ProviderFamily.CLAUDE.value: ("sonnet",),
                ProviderFamily.LOCAL.value: ("deterministic-reader",),
            },
        ),
        canonical_prompt_id=_prompt_id(WorkflowRole.EXECUTOR),
        canonical_skill_names=(_skill_name(WorkflowRole.EXECUTOR),),
    ),
    RoleSpec(
        role_id=WorkflowRole.ANALYST,
        mission="Analyze run outcomes, surface anomalies, and relate results back to the experiment intent.",
        required_inputs=("run_manifest", "metrics", "artifacts"),
        required_outputs=("result_summary",),
        artifact_contracts=(
            _artifact_contract(
                WorkflowRole.ANALYST,
                "result_summary",
                "Structured analysis of run outcomes and anomalies.",
            ),
        ),
        allowed_tools=("filesystem", "python_exec"),
        forbidden_tools=("experiment_runner",),
        success_criteria=(
            "Result summary explains notable outcomes and anomalies.",
            "Recommended next actions are specific.",
        ),
        review_checklist=(
            "Separate observed outcomes from speculation.",
            "Reference run evidence when possible.",
        ),
        default_capability_class=CapabilityClass.SYNTHESIS,
        default_provider_preference=_REASONING_DEFAULT,
        fallback_provider_preference=_REASONING_FALLBACK,
        canonical_prompt_id=_prompt_id(WorkflowRole.ANALYST),
        canonical_skill_names=(_skill_name(WorkflowRole.ANALYST),),
    ),
    RoleSpec(
        role_id=WorkflowRole.REVIEWER,
        mission="Review structure, quality, and blocking issues before downstream publication or approval.",
        required_inputs=("artifacts", "claims", "review_scope"),
        required_outputs=("review_report",),
        artifact_contracts=(
            _artifact_contract(
                WorkflowRole.REVIEWER,
                "review_report",
                "Quality review report covering blocking issues and decision.",
            ),
        ),
        allowed_tools=("filesystem",),
        forbidden_tools=("experiment_runner",),
        success_criteria=(
            "Decision and blocking issues are explicit.",
            "Human approvals are requested where required.",
        ),
        review_checklist=(
            "Flag missing baselines and missing evidence.",
            "Do not hide uncertainty behind a binary decision.",
        ),
        default_capability_class=CapabilityClass.REVIEW,
        default_provider_preference=_REASONING_DEFAULT,
        fallback_provider_preference=_REASONING_FALLBACK,
        canonical_prompt_id=_prompt_id(WorkflowRole.REVIEWER),
        canonical_skill_names=(_skill_name(WorkflowRole.REVIEWER),),
    ),
    RoleSpec(
        role_id=WorkflowRole.VERIFIER,
        mission="Check evidence chains, methodological validity, and verification state honestly.",
        required_inputs=("run_manifest", "claims", "freeze_state"),
        required_outputs=("verification_report",),
        artifact_contracts=(
            _artifact_contract(
                WorkflowRole.VERIFIER,
                "verification_report",
                "Evidence-chain and methodological verification report.",
            ),
        ),
        allowed_tools=("filesystem",),
        forbidden_tools=("experiment_runner",),
        success_criteria=(
            "Verification status is explicit and honest.",
            "Missing evidence is called out rather than guessed.",
        ),
        review_checklist=(
            "Do not claim verification beyond recorded checks.",
            "Link recommendations to missing evidence or missing artifacts.",
        ),
        default_capability_class=CapabilityClass.VERIFICATION,
        default_provider_preference=_REASONING_DEFAULT,
        fallback_provider_preference=_REASONING_FALLBACK,
        canonical_prompt_id=_prompt_id(WorkflowRole.VERIFIER),
        canonical_skill_names=(_skill_name(WorkflowRole.VERIFIER),),
    ),
    RoleSpec(
        role_id=WorkflowRole.PUBLISHER,
        mission="Turn frozen evidence, approved claims, and imported result packages into publishable drafts or sections.",
        required_inputs=("frozen_claims", "supporting_artifacts", "writing_scope", "evidence_sources"),
        required_outputs=("paper_draft",),
        artifact_contracts=(
            _artifact_contract(
                WorkflowRole.PUBLISHER,
                "paper_draft",
                "Draft section or paper content aligned with frozen evidence.",
            ),
        ),
        allowed_tools=("filesystem",),
        forbidden_tools=("experiment_runner",),
        success_criteria=(
            "Draft structure matches requested scope.",
            "Claims stay aligned with frozen evidence.",
        ),
        review_checklist=(
            "Avoid unsupported claims.",
            "Keep traceability to supporting claims or artifacts.",
        ),
        default_capability_class=CapabilityClass.PUBLISHING,
        default_provider_preference=_REASONING_DEFAULT,
        fallback_provider_preference=_REASONING_FALLBACK,
        canonical_prompt_id=_prompt_id(WorkflowRole.PUBLISHER),
        canonical_skill_names=(_skill_name(WorkflowRole.PUBLISHER),),
    ),
    RoleSpec(
        role_id=WorkflowRole.ARCHIVIST,
        mission="Curate archive entries, lessons, and provenance notes for future reuse.",
        required_inputs=("run_summary", "lessons", "provenance_notes"),
        required_outputs=("archive_entry",),
        artifact_contracts=(
            _artifact_contract(
                WorkflowRole.ARCHIVIST,
                "archive_entry",
                "Registry curation note with lesson/provenance linkage.",
            ),
        ),
        allowed_tools=("filesystem",),
        forbidden_tools=("experiment_runner", "shell"),
        success_criteria=(
            "Archive entry links lessons and provenance cleanly.",
            "Curated lessons remain reusable across runs.",
        ),
        review_checklist=(
            "Separate durable lessons from transient logs.",
            "Preserve source references where available.",
        ),
        default_capability_class=CapabilityClass.ARCHIVAL,
        default_provider_preference=_ARCHIVAL_DEFAULT,
        fallback_provider_preference=RoleProviderPreference(
            family_priority=(
                ProviderFamily.LOCAL.value,
                ProviderFamily.CLAUDE.value,
                ProviderFamily.CODEX.value,
            ),
            model_priority={
                ProviderFamily.LOCAL.value: ("deterministic-reader",),
                ProviderFamily.CLAUDE.value: ("sonnet",),
                ProviderFamily.CODEX.value: ("gpt-5.4",),
            },
        ),
        canonical_prompt_id=_prompt_id(WorkflowRole.ARCHIVIST),
        canonical_skill_names=(_skill_name(WorkflowRole.ARCHIVIST),),
    ),
)

ROLE_REGISTRY = RoleRegistry(ROLE_SPECS)
ROLE_SPECS_BY_NAME: dict[str, RoleSpec] = {spec.role_name: spec for spec in ROLE_SPECS}
ROLE_ARTIFACT_CONTRACTS: dict[str, tuple[RoleArtifactContract, ...]] = {
    spec.role_name: spec.artifact_contracts for spec in ROLE_SPECS
}


def get_role_spec(role: WorkflowRole | str) -> RoleSpec:
    return ROLE_REGISTRY.require(role)


def role_routing_policy_for_role(role: WorkflowRole | str) -> RoleRoutingPolicy:
    spec = get_role_spec(role)
    return RoleRoutingPolicy(
        role_name=spec.role_name,
        capability_class=spec.default_capability_class.value,
        family_priority=list(spec.default_provider_preference.family_priority),
        family_model_priority={
            family: list(models)
            for family, models in spec.default_provider_preference.model_priority.items()
        },
        fallback_chain=FallbackChain(families=list(spec.default_provider_preference.family_priority)),
        invocation_budget_policy=InvocationBudgetPolicy(
            prefer_low_cost=True,
            allow_expensive_upgrade=False,
            max_attempts_per_invocation=max(2, len(spec.default_provider_preference.family_priority)),
        ),
    )


def _binding(
    *,
    agent_name: str,
    default_role: WorkflowRole,
    secondary_roles: tuple[WorkflowRole, ...] = (),
    task_kind_roles: dict[str, WorkflowRole] | None = None,
) -> AgentRoleBinding:
    return AgentRoleBinding(
        agent_name=agent_name,
        default_role=default_role,
        secondary_roles=secondary_roles,
        task_kind_roles=task_kind_roles or {},
        artifact_contracts=ROLE_ARTIFACT_CONTRACTS,
        role_registry=ROLE_REGISTRY,
    )


def reader_role_binding() -> AgentRoleBinding:
    return _binding(
        agent_name="reader_agent",
        default_role=WorkflowRole.LIBRARIAN,
        secondary_roles=(WorkflowRole.SCOPER,),
        task_kind_roles={
            "paper_ingest": WorkflowRole.LIBRARIAN,
            "repo_ingest": WorkflowRole.LIBRARIAN,
            "read_source": WorkflowRole.SCOPER,
        },
    )


def mapper_role_binding() -> AgentRoleBinding:
    return _binding(
        agent_name="mapper_agent",
        default_role=WorkflowRole.SYNTHESIZER,
    )


def builder_role_binding() -> AgentRoleBinding:
    return _binding(
        agent_name="builder_agent",
        default_role=WorkflowRole.EXPERIMENT_DESIGNER,
        secondary_roles=(WorkflowRole.HYPOTHESIST, WorkflowRole.EXECUTOR),
        task_kind_roles={
            "build_spec": WorkflowRole.HYPOTHESIST,
            "implement_experiment": WorkflowRole.EXECUTOR,
            "reproduce_baseline": WorkflowRole.EXECUTOR,
        },
    )


def reviewer_role_binding() -> AgentRoleBinding:
    return _binding(
        agent_name="reviewer_agent",
        default_role=WorkflowRole.REVIEWER,
    )


def writer_role_binding() -> AgentRoleBinding:
    return _binding(
        agent_name="writer_agent",
        default_role=WorkflowRole.PUBLISHER,
    )


def style_role_binding() -> AgentRoleBinding:
    return _binding(
        agent_name="style_agent",
        default_role=WorkflowRole.PUBLISHER,
    )


def analyst_role_binding() -> AgentRoleBinding:
    return _binding(
        agent_name="analyst_agent",
        default_role=WorkflowRole.ANALYST,
    )


def verifier_role_binding() -> AgentRoleBinding:
    return _binding(
        agent_name="verifier_agent",
        default_role=WorkflowRole.VERIFIER,
    )


def archivist_role_binding() -> AgentRoleBinding:
    return _binding(
        agent_name="archivist_agent",
        default_role=WorkflowRole.ARCHIVIST,
    )
