from __future__ import annotations

from dataclasses import dataclass

from app.agents.analyst import AnalystAgent
from app.agents.archivist import ArchivistAgent
from app.agents.branch_manager import BranchManagerAgent
from app.agents.builder import BuilderAgent
from app.agents.mapper import MapperAgent
from app.agents.orchestrator import Orchestrator
from app.agents.reader import ReaderAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.style import StyleAgent
from app.agents.verifier import VerifierAgent
from app.agents.writer import WriterAgent
from app.core.config import AppConfig
from app.core.paths import WorkspacePaths
from app.db.repositories.sa_project_repository import SAProjectRepository
from app.db.repositories.sa_task_repository import SATaskRepository
from app.db.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.db.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.db.session import create_session_factory
from app.db.sqlite import SQLiteDatabase
from app.providers.claude_provider import ClaudeProvider
from app.providers.codex_provider import CodexProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.health import ProviderHealthService
from app.providers.local_provider import LocalProvider
from app.providers.registry import ProviderRegistry
from app.roles import WorkflowRole, role_routing_policy_for_role
from app.roles.prompts import ROLE_PROMPT_REGISTRY, RolePromptRegistry
from app.routing.models import (
    AgentRoutingPolicy,
    DispatchProfile,
    ModelProfile,
    ProviderSpec,
    RoleRoutingPolicy,
)
from app.routing.provider_router import ProviderInvocationService
from app.routing.resolver import RoutingResolver
from app.skills import ROLE_SKILL_REGISTRY, RoleSkillRegistry
from app.services.approval_service import ApprovalService
from app.services.activity_service import ActivityService
from app.services.artifact_annotation_service import ArtifactAnnotationService
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.services.claim_service import ClaimService
from app.services.checkpoint_service import CheckpointService
from app.services.experiment_manager import ExperimentManager
from app.services.experiment_registry import ExperimentRegistry
from app.services.freeze_service import FreezeService
from app.services.gap_map_service import GapMapService
from app.services.lessons_service import LessonsService
from app.services.kb_service import KnowledgeBaseService
from app.services.operator_inspection_service import OperatorInspectionService
from app.services.paper_card_service import PaperCardService
from app.services.project_service import ProjectService
from app.services.research_guide_service import ResearchGuideService
from app.services.provenance_service import ProvenanceService
from app.services.run_service import RunService
from app.services.task_service import TaskService
from app.services.verification_service import VerificationService
from app.tools.experiment_runner import ExperimentRunnerTool
from app.tools.arxiv_fetcher import ArxivFetcherTool
from app.tools.filesystem import FilesystemTool
from app.tools.git_tool import GitTool
from app.tools.mcp_adapter import MCPAdapterTool
from app.tools.paper_search import PaperSearchTool
from app.tools.query_decomposer import QueryDecomposerTool
from app.tools.semantic_scholar import SemanticScholarSearchTool
from app.tools.citation_verifier import CitationVerifierTool
from app.tools.pdf_parse import PDFParseTool
from app.tools.python_exec import PythonExecTool
from app.tools.registry import ToolRegistry
from app.tools.shell_tool import ShellTool


@dataclass
class RuntimeServices:
    activity_service: ActivityService
    checkpoint_service: CheckpointService
    project_service: ProjectService
    task_service: TaskService
    claim_service: ClaimService
    run_service: RunService
    freeze_service: FreezeService
    paper_card_service: PaperCardService
    gap_map_service: GapMapService
    approval_service: ApprovalService
    artifact_service: ArtifactService
    artifact_annotation_service: ArtifactAnnotationService
    audit_service: AuditService
    experiment_manager: ExperimentManager
    lessons_service: LessonsService
    verification_service: VerificationService
    kb_service: KnowledgeBaseService
    provenance_service: ProvenanceService
    operator_inspection_service: OperatorInspectionService
    tool_registry: ToolRegistry
    provider_registry: ProviderRegistry
    provider_health_service: ProviderHealthService
    provider_invocation_service: ProviderInvocationService
    routing_resolver: RoutingResolver
    role_prompt_registry: RolePromptRegistry
    role_skill_registry: RoleSkillRegistry
    orchestrator: Orchestrator
    research_guide_service: ResearchGuideService


def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(FilesystemTool())
    registry.register(ShellTool())
    registry.register(PythonExecTool())
    registry.register(GitTool())
    registry.register(ExperimentRunnerTool())
    registry.register(ArxivFetcherTool())
    registry.register(PaperSearchTool())
    registry.register(SemanticScholarSearchTool())
    registry.register(CitationVerifierTool())
    registry.register(PDFParseTool())
    registry.register(MCPAdapterTool())
    return registry


def build_provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register("claude", ClaudeProvider)
    registry.register("codex", CodexProvider)
    registry.register("gemini", GeminiProvider)
    registry.register("local", LocalProvider)
    return registry


def build_system_dispatch_profile(config: AppConfig) -> DispatchProfile:
    provider_name = config.provider_name.lower()
    return DispatchProfile(
        provider=ProviderSpec(
            provider_name=provider_name,
            model=config.provider_model or None,
        ),
        model_profile=ModelProfile(
            profile_name="system-default",
            provider_name=provider_name,
            model=config.provider_model or None,
            max_steps=config.max_steps,
        ),
        max_steps=config.max_steps,
        metadata={
            "source": "env_explicit"
            if config.provider_explicit or config.provider_model_explicit
            else "implicit_default"
        },
    )


def build_agent_routing_policy(
    *,
    agent_name: str,
    default_role_policy: RoleRoutingPolicy,
    task_kind_role_policies: dict[str, RoleRoutingPolicy] | None = None,
    fallback_provider: ProviderSpec | None = None,
    fallback_model_profile: ModelProfile | None = None,
) -> AgentRoutingPolicy:
    return AgentRoutingPolicy(
        agent_name=agent_name,
        fallback_provider=fallback_provider,
        fallback_model_profile=fallback_model_profile,
        default_role_policy=default_role_policy,
        task_kind_role_policies=task_kind_role_policies or {},
    )


def build_role_routing_policy(role_name: str) -> RoleRoutingPolicy:
    return role_routing_policy_for_role(WorkflowRole(role_name))


def build_fallback_provider(config: AppConfig) -> ProviderSpec:
    return ProviderSpec(
        provider_name=config.provider_name.lower(),
        model=config.provider_model or None,
    )


def build_fallback_model_profile(config: AppConfig, agent_name: str) -> ModelProfile:
    return ModelProfile(
        profile_name=f"{agent_name}-fallback",
        provider_name=config.provider_name.lower(),
        model=config.provider_model or None,
        max_steps=config.max_steps,
    )


def build_orchestrator(config: AppConfig, services: RuntimeServices) -> Orchestrator:
    default_provider = services.provider_registry.get(config.provider_name.lower())
    tool_registry = services.tool_registry

    orchestrator = Orchestrator(
        services.task_service,
        project_service=services.project_service,
        routing_resolver=services.routing_resolver,
        lessons_service=services.lessons_service,
        artifacts_dir=WorkspacePaths.from_root(config.workspace_root).artifacts_dir,
        activity_service=services.activity_service,
        checkpoint_service=services.checkpoint_service,
    )
    orchestrator.register_agent(
        ReaderAgent(
            default_provider,
            kb_service=services.kb_service,
            paper_card_service=services.paper_card_service,
            artifact_service=services.artifact_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
            provider_registry=services.provider_registry,
            provider_invocation_service=services.provider_invocation_service,
            role_prompt_registry=services.role_prompt_registry,
            role_skill_registry=services.role_skill_registry,
            routing_policy=build_agent_routing_policy(
                agent_name="reader_agent",
                default_role_policy=build_role_routing_policy("librarian"),
                task_kind_role_policies={"read_source": build_role_routing_policy("scoper")},
                fallback_provider=build_fallback_provider(config),
                fallback_model_profile=build_fallback_model_profile(config, "reader_agent"),
            ),
        ),
        handles={"paper_ingest", "repo_ingest", "read_source"},
    )
    orchestrator.register_agent(
        MapperAgent(
            default_provider,
            gap_map_service=services.gap_map_service,
            paper_card_service=services.paper_card_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
            provider_registry=services.provider_registry,
            provider_invocation_service=services.provider_invocation_service,
            role_prompt_registry=services.role_prompt_registry,
            role_skill_registry=services.role_skill_registry,
            routing_policy=build_agent_routing_policy(
                agent_name="mapper_agent",
                default_role_policy=build_role_routing_policy("synthesizer"),
                fallback_provider=build_fallback_provider(config),
                fallback_model_profile=build_fallback_model_profile(config, "mapper_agent"),
            ),
        ),
        handles={"gap_mapping", "map_gaps"},
    )
    orchestrator.register_agent(
        BranchManagerAgent(
            default_provider,
            task_service=services.task_service,
            checkpoint_service=services.checkpoint_service,
            freeze_service=services.freeze_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
            provider_registry=services.provider_registry,
            provider_invocation_service=services.provider_invocation_service,
            role_prompt_registry=services.role_prompt_registry,
            role_skill_registry=services.role_skill_registry,
            routing_policy=build_agent_routing_policy(
                agent_name="branch_manager_agent",
                default_role_policy=build_role_routing_policy("analyst"),
                fallback_provider=build_fallback_provider(config),
                fallback_model_profile=build_fallback_model_profile(config, "branch_manager_agent"),
            ),
        ),
        handles={"branch_plan", "branch_review"},
    )
    orchestrator.register_agent(
        BuilderAgent(
            default_provider,
            artifact_service=services.artifact_service,
            claim_service=services.claim_service,
            run_service=services.run_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
            provider_registry=services.provider_registry,
            provider_invocation_service=services.provider_invocation_service,
            role_prompt_registry=services.role_prompt_registry,
            role_skill_registry=services.role_skill_registry,
            routing_policy=build_agent_routing_policy(
                agent_name="builder_agent",
                default_role_policy=build_role_routing_policy("experiment_designer"),
                task_kind_role_policies={
                    "implement_experiment": build_role_routing_policy("executor"),
                    "reproduce_baseline": build_role_routing_policy("executor"),
                    "build_spec": build_role_routing_policy("hypothesist"),
                },
                fallback_provider=build_fallback_provider(config),
                fallback_model_profile=build_fallback_model_profile(config, "builder_agent"),
            ),
        ),
        handles={"build_spec", "implement_experiment", "reproduce_baseline"},
    )
    orchestrator.register_agent(
        ReviewerAgent(
            default_provider,
            kb_service=services.kb_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
            provider_registry=services.provider_registry,
            provider_invocation_service=services.provider_invocation_service,
            role_prompt_registry=services.role_prompt_registry,
            role_skill_registry=services.role_skill_registry,
            routing_policy=build_agent_routing_policy(
                agent_name="reviewer_agent",
                default_role_policy=build_role_routing_policy("reviewer"),
                fallback_provider=build_fallback_provider(config),
                fallback_model_profile=build_fallback_model_profile(config, "reviewer_agent"),
            ),
        ),
        handles={"review_build", "audit_run", "gap_debate"},
    )
    orchestrator.register_agent(
        WriterAgent(
            default_provider,
            artifact_service=services.artifact_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
            provider_registry=services.provider_registry,
            provider_invocation_service=services.provider_invocation_service,
            role_prompt_registry=services.role_prompt_registry,
            role_skill_registry=services.role_skill_registry,
            routing_policy=build_agent_routing_policy(
                agent_name="writer_agent",
                default_role_policy=build_role_routing_policy("publisher"),
                fallback_provider=build_fallback_provider(config),
                fallback_model_profile=build_fallback_model_profile(config, "writer_agent"),
            ),
        ),
        handles={"write_draft", "write_section"},
    )
    orchestrator.register_agent(
        StyleAgent(
            default_provider,
            artifact_service=services.artifact_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
            provider_registry=services.provider_registry,
            provider_invocation_service=services.provider_invocation_service,
            role_prompt_registry=services.role_prompt_registry,
            role_skill_registry=services.role_skill_registry,
            routing_policy=build_agent_routing_policy(
                agent_name="style_agent",
                default_role_policy=build_role_routing_policy("publisher"),
                fallback_provider=build_fallback_provider(config),
                fallback_model_profile=build_fallback_model_profile(config, "style_agent"),
            ),
        ),
        handles={"style_pass", "polish_draft"},
    )
    orchestrator.register_agent(
        AnalystAgent(
            default_provider,
            kb_service=services.kb_service,
            artifact_service=services.artifact_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
            provider_registry=services.provider_registry,
            provider_invocation_service=services.provider_invocation_service,
            role_prompt_registry=services.role_prompt_registry,
            role_skill_registry=services.role_skill_registry,
            routing_policy=build_agent_routing_policy(
                agent_name="analyst_agent",
                default_role_policy=build_role_routing_policy("analyst"),
                fallback_provider=build_fallback_provider(config),
                fallback_model_profile=build_fallback_model_profile(config, "analyst_agent"),
            ),
        ),
        handles={"analyze_results", "analyze_run"},
    )
    orchestrator.register_agent(
        VerifierAgent(
            default_provider,
            verification_service=services.verification_service,
            artifact_service=services.artifact_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
            provider_registry=services.provider_registry,
            provider_invocation_service=services.provider_invocation_service,
            role_prompt_registry=services.role_prompt_registry,
            role_skill_registry=services.role_skill_registry,
            routing_policy=build_agent_routing_policy(
                agent_name="verifier_agent",
                default_role_policy=build_role_routing_policy("verifier"),
                fallback_provider=build_fallback_provider(config),
                fallback_model_profile=build_fallback_model_profile(config, "verifier_agent"),
            ),
        ),
        handles={"verify_evidence", "verify_claim", "verify_results"},
    )
    orchestrator.register_agent(
        ArchivistAgent(
            default_provider,
            lessons_service=services.lessons_service,
            artifact_service=services.artifact_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
            provider_registry=services.provider_registry,
            provider_invocation_service=services.provider_invocation_service,
            role_prompt_registry=services.role_prompt_registry,
            role_skill_registry=services.role_skill_registry,
            routing_policy=build_agent_routing_policy(
                agent_name="archivist_agent",
                default_role_policy=build_role_routing_policy("archivist"),
                fallback_provider=build_fallback_provider(config),
                fallback_model_profile=build_fallback_model_profile(config, "archivist_agent"),
            ),
        ),
        handles={"archive_research", "archive_run", "record_lessons"},
    )
    return orchestrator


def build_runtime_services(config: AppConfig) -> RuntimeServices:
    workspace_paths = WorkspacePaths.from_root(config.workspace_root)
    sqlite_database: SQLiteDatabase | None = None
    if config.database_url:
        session_factory = create_session_factory(config.database_url)
        project_repository = SAProjectRepository(session_factory)
        task_repository = SATaskRepository(session_factory)
    else:
        sqlite_database = SQLiteDatabase(config.db_path)
        sqlite_database.initialize()
        project_repository = SQLiteProjectRepository(sqlite_database)
        task_repository = SQLiteTaskRepository(sqlite_database)

    claim_service = ClaimService(workspace_paths.registry_file("claims.jsonl"))
    run_service = RunService(workspace_paths.registry_file("runs.jsonl"))
    freeze_service = FreezeService(workspace_paths.freezes_dir)
    activity_service = ActivityService(
        database=sqlite_database,
        events_path=workspace_paths.state_dir / "run_events.jsonl",
        conversations_path=workspace_paths.state_dir / "conversation_messages.jsonl",
    )
    checkpoint_service = CheckpointService(workspace_paths.artifacts_dir / "checkpoints")
    approval_service = ApprovalService(
        workspace_paths.registry_file("approvals.jsonl"),
        database=sqlite_database,
    )
    artifact_service = ArtifactService(
        workspace_paths.registry_file("artifacts.jsonl"),
        workspace_root=workspace_paths.root,
    )
    paper_card_service = PaperCardService(
        workspace_paths.registry_file("paper_cards.jsonl"),
        database=sqlite_database,
    )
    gap_map_service = GapMapService(
        workspace_paths.registry_file("gap_maps.jsonl"),
        database=sqlite_database,
    )
    artifact_annotation_service = ArtifactAnnotationService(
        workspace_paths.registry_file("artifact_annotations.jsonl")
    )
    lessons_service = LessonsService(
        workspace_paths.registry_file("lessons.jsonl"),
        database=sqlite_database,
    )
    audit_service = AuditService(claim_service, run_service)
    verification_service = VerificationService(
        run_service=run_service,
        artifact_service=artifact_service,
        claim_service=claim_service,
        freeze_service=freeze_service,
        registry_path=workspace_paths.registry_file("verifications.jsonl"),
    )
    project_service = ProjectService(project_repository)
    task_service = TaskService(task_repository, activity_service=activity_service)
    provider_registry = build_provider_registry()
    default_provider = provider_registry.get(config.provider_name.lower())
    tool_registry = build_tool_registry()
    tool_registry.register(QueryDecomposerTool(default_provider, model=config.provider_model or None))
    provider_health_service = ProviderHealthService(
        cooldown_seconds=config.provider_cooldown_seconds,
        disabled_families=set(config.disabled_provider_families),
        state_path=workspace_paths.provider_health_state_file,
    )
    provider_invocation_service = ProviderInvocationService(
        provider_registry,
        provider_health_service,
    )
    routing_resolver = RoutingResolver(build_system_dispatch_profile(config))
    storage_boundary = workspace_paths.storage_boundary(
        database_backend="postgres" if config.database_url else "sqlite",
        database_location=config.database_url or config.db_path,
    )
    provenance_service = ProvenanceService(
        artifact_service=artifact_service,
        annotation_service=artifact_annotation_service,
        audit_service=audit_service,
        verification_service=verification_service,
        run_service=run_service,
        claim_service=claim_service,
        freeze_service=freeze_service,
    )
    placeholder_orchestrator = Orchestrator(
        task_service,
        project_service=project_service,
        routing_resolver=routing_resolver,
        lessons_service=lessons_service,
        artifacts_dir=workspace_paths.artifacts_dir,
        activity_service=activity_service,
        checkpoint_service=checkpoint_service,
    )
    services = RuntimeServices(
        activity_service=activity_service,
        checkpoint_service=checkpoint_service,
        project_service=project_service,
        task_service=task_service,
        claim_service=claim_service,
        run_service=run_service,
        freeze_service=freeze_service,
        paper_card_service=paper_card_service,
        gap_map_service=gap_map_service,
        approval_service=approval_service,
        artifact_service=artifact_service,
        artifact_annotation_service=artifact_annotation_service,
        audit_service=audit_service,
        experiment_manager=ExperimentManager(
            registry=ExperimentRegistry(workspace_paths.experiments_dir),
            task_service=task_service,
            run_service=run_service,
            freeze_service=freeze_service,
            approval_service=approval_service,
        ),
        lessons_service=lessons_service,
        verification_service=verification_service,
        kb_service=KnowledgeBaseService(workspace_paths.registry_dir / "kb"),
        provenance_service=provenance_service,
        operator_inspection_service=OperatorInspectionService(
            project_service=project_service,
            task_service=task_service,
            run_service=run_service,
            artifact_service=artifact_service,
            artifact_annotation_service=artifact_annotation_service,
            paper_card_service=paper_card_service,
            gap_map_service=gap_map_service,
            freeze_service=freeze_service,
            provenance_service=provenance_service,
            orchestrator=placeholder_orchestrator,
            provider_registry=provider_registry,
            provider_health_service=provider_health_service,
            storage_boundary=storage_boundary,
        ),
        tool_registry=tool_registry,
        provider_registry=provider_registry,
        provider_health_service=provider_health_service,
        provider_invocation_service=provider_invocation_service,
        routing_resolver=routing_resolver,
        role_prompt_registry=ROLE_PROMPT_REGISTRY,
        role_skill_registry=ROLE_SKILL_REGISTRY,
        orchestrator=placeholder_orchestrator,
        research_guide_service=ResearchGuideService(
            project_service=project_service,
            task_service=task_service,
            freeze_service=freeze_service,
            gap_map_service=gap_map_service,
            paper_card_service=paper_card_service,
            provider_registry=provider_registry,
            kb_service=KnowledgeBaseService(workspace_paths.registry_dir / "kb"),
            tool_registry=tool_registry,
            orchestrator=placeholder_orchestrator,
            activity_service=activity_service,
        ),
    )
    services.orchestrator = build_orchestrator(config, services)
    services.research_guide_service = ResearchGuideService(
        project_service=project_service,
        task_service=task_service,
        freeze_service=freeze_service,
        gap_map_service=gap_map_service,
        paper_card_service=paper_card_service,
        provider_registry=provider_registry,
        kb_service=services.kb_service,
        tool_registry=tool_registry,
        orchestrator=services.orchestrator,
        activity_service=activity_service,
    )
    services.operator_inspection_service = OperatorInspectionService(
        project_service=project_service,
        task_service=task_service,
        run_service=run_service,
        artifact_service=artifact_service,
        artifact_annotation_service=artifact_annotation_service,
        paper_card_service=services.paper_card_service,
        gap_map_service=services.gap_map_service,
        freeze_service=freeze_service,
        provenance_service=services.provenance_service,
        orchestrator=services.orchestrator,
        provider_registry=provider_registry,
        provider_health_service=provider_health_service,
        storage_boundary=storage_boundary,
    )
    return services
