from __future__ import annotations

from dataclasses import dataclass

from app.agents.builder import BuilderAgent
from app.agents.mapper import MapperAgent
from app.agents.orchestrator import Orchestrator
from app.agents.reader import ReaderAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.style import StyleAgent
from app.agents.writer import WriterAgent
from app.core.config import AppConfig
from app.db.repositories.sa_project_repository import SAProjectRepository
from app.db.repositories.sa_task_repository import SATaskRepository
from app.db.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.db.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.db.session import create_session_factory
from app.db.sqlite import SQLiteDatabase
from app.providers.claude_provider import ClaudeProvider
from app.providers.codex_provider import CodexProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.local_provider import LocalProvider
from app.providers.registry import ProviderRegistry
from app.routing.models import AgentRoutingPolicy, DispatchProfile, ModelProfile, ProviderSpec
from app.routing.resolver import RoutingResolver
from app.services.approval_service import ApprovalService
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.services.claim_service import ClaimService
from app.services.experiment_manager import ExperimentManager
from app.services.experiment_registry import ExperimentRegistry
from app.services.freeze_service import FreezeService
from app.services.gap_map_service import GapMapService
from app.services.lessons_service import LessonsService
from app.services.paper_card_service import PaperCardService
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.services.task_service import TaskService
from app.services.verification_service import VerificationService
from app.tools.experiment_runner import ExperimentRunnerTool
from app.tools.filesystem import FilesystemTool
from app.tools.git_tool import GitTool
from app.tools.mcp_adapter import MCPAdapterTool
from app.tools.paper_search import PaperSearchTool
from app.tools.pdf_parse import PDFParseTool
from app.tools.python_exec import PythonExecTool
from app.tools.registry import ToolRegistry
from app.tools.shell_tool import ShellTool


@dataclass
class RuntimeServices:
    project_service: ProjectService
    task_service: TaskService
    claim_service: ClaimService
    run_service: RunService
    freeze_service: FreezeService
    paper_card_service: PaperCardService
    gap_map_service: GapMapService
    approval_service: ApprovalService
    artifact_service: ArtifactService
    audit_service: AuditService
    experiment_manager: ExperimentManager
    lessons_service: LessonsService
    verification_service: VerificationService
    tool_registry: ToolRegistry
    provider_registry: ProviderRegistry
    routing_resolver: RoutingResolver
    orchestrator: Orchestrator


def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(FilesystemTool())
    registry.register(ShellTool())
    registry.register(PythonExecTool())
    registry.register(GitTool())
    registry.register(ExperimentRunnerTool())
    registry.register(PaperSearchTool())
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
        metadata={"source": "env"},
    )


def build_agent_routing_policy(
    config: AppConfig,
    agent_name: str,
    model: str | None = None,
) -> AgentRoutingPolicy:
    provider_name = config.provider_name.lower()
    effective_model = model or config.provider_model or None
    return AgentRoutingPolicy(
        agent_name=agent_name,
        fallback_provider=ProviderSpec(
            provider_name=provider_name,
            model=effective_model,
        ),
        fallback_model_profile=ModelProfile(
            profile_name=f"{agent_name}-fallback",
            provider_name=provider_name,
            model=effective_model,
            max_steps=config.max_steps,
        ),
    )


def build_orchestrator(config: AppConfig, services: RuntimeServices) -> Orchestrator:
    default_provider = services.provider_registry.get(config.provider_name.lower())
    tool_registry = services.tool_registry

    orchestrator = Orchestrator(
        services.task_service,
        project_service=services.project_service,
        routing_resolver=services.routing_resolver,
        lessons_service=services.lessons_service,
    )
    orchestrator.register_agent(
        ReaderAgent(
            default_provider,
            paper_card_service=services.paper_card_service,
            artifact_service=services.artifact_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
            provider_registry=services.provider_registry,
            routing_policy=build_agent_routing_policy(config, "reader_agent", config.provider_model or None),
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
            routing_policy=build_agent_routing_policy(config, "mapper_agent", config.provider_model or None),
        ),
        handles={"gap_mapping", "map_gaps"},
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
            routing_policy=build_agent_routing_policy(config, "builder_agent", config.provider_model or None),
        ),
        handles={"build_spec", "implement_experiment", "reproduce_baseline"},
    )
    orchestrator.register_agent(
        ReviewerAgent(
            default_provider,
            model=config.provider_model or None,
            tool_registry=tool_registry,
            provider_registry=services.provider_registry,
            routing_policy=build_agent_routing_policy(config, "reviewer_agent", config.provider_model or None),
        ),
        handles={"review_build", "audit_run"},
    )
    orchestrator.register_agent(
        WriterAgent(
            default_provider,
            artifact_service=services.artifact_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
            provider_registry=services.provider_registry,
            routing_policy=build_agent_routing_policy(config, "writer_agent", config.provider_model or None),
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
            routing_policy=build_agent_routing_policy(config, "style_agent", config.provider_model or None),
        ),
        handles={"style_pass", "polish_draft"},
    )
    return orchestrator


def build_runtime_services(config: AppConfig) -> RuntimeServices:
    if config.database_url:
        session_factory = create_session_factory(config.database_url)
        project_repository = SAProjectRepository(session_factory)
        task_repository = SATaskRepository(session_factory)
    else:
        database = SQLiteDatabase(config.db_path)
        database.initialize()
        project_repository = SQLiteProjectRepository(database)
        task_repository = SQLiteTaskRepository(database)

    claim_service = ClaimService()
    run_service = RunService()
    freeze_service = FreezeService()
    approval_service = ApprovalService()
    artifact_service = ArtifactService()
    lessons_service = LessonsService()
    verification_service = VerificationService(
        run_service=run_service,
        artifact_service=artifact_service,
        claim_service=claim_service,
        freeze_service=freeze_service,
    )
    project_service = ProjectService(project_repository)
    task_service = TaskService(task_repository)
    provider_registry = build_provider_registry()
    routing_resolver = RoutingResolver(build_system_dispatch_profile(config))
    services = RuntimeServices(
        project_service=project_service,
        task_service=task_service,
        claim_service=claim_service,
        run_service=run_service,
        freeze_service=freeze_service,
        paper_card_service=PaperCardService(),
        gap_map_service=GapMapService(),
        approval_service=approval_service,
        artifact_service=artifact_service,
        audit_service=AuditService(claim_service, run_service),
        experiment_manager=ExperimentManager(
            registry=ExperimentRegistry(),
            task_service=task_service,
            run_service=run_service,
            freeze_service=freeze_service,
            approval_service=approval_service,
        ),
        lessons_service=lessons_service,
        verification_service=verification_service,
        tool_registry=build_tool_registry(),
        provider_registry=provider_registry,
        routing_resolver=routing_resolver,
        orchestrator=Orchestrator(
            task_service,
            project_service=project_service,
            routing_resolver=routing_resolver,
            lessons_service=lessons_service,
        ),
    )
    services.orchestrator = build_orchestrator(config, services)
    return services
