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
from app.services.approval_service import ApprovalService
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.services.claim_service import ClaimService
from app.services.freeze_service import FreezeService
from app.services.gap_map_service import GapMapService
from app.services.paper_card_service import PaperCardService
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.services.task_service import TaskService
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
    tool_registry: ToolRegistry
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


def build_provider(config: AppConfig):
    provider_name = config.provider_name.lower()
    if provider_name == "codex":
        return CodexProvider()
    if provider_name == "gemini":
        return GeminiProvider()
    if provider_name == "local":
        return LocalProvider()
    return ClaudeProvider()


def build_orchestrator(config: AppConfig, services: RuntimeServices) -> Orchestrator:
    provider = build_provider(config)
    tool_registry = services.tool_registry

    orchestrator = Orchestrator(services.task_service)
    orchestrator.register_agent(
        ReaderAgent(
            provider,
            paper_card_service=services.paper_card_service,
            artifact_service=services.artifact_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
        ),
        handles={"paper_ingest", "repo_ingest", "read_source"},
    )
    orchestrator.register_agent(
        MapperAgent(
            provider,
            gap_map_service=services.gap_map_service,
            paper_card_service=services.paper_card_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
        ),
        handles={"gap_mapping", "map_gaps"},
    )
    orchestrator.register_agent(
        BuilderAgent(
            provider,
            artifact_service=services.artifact_service,
            claim_service=services.claim_service,
            run_service=services.run_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
        ),
        handles={"build_spec", "implement_experiment", "reproduce_baseline"},
    )
    orchestrator.register_agent(
        ReviewerAgent(
            provider,
            model=config.provider_model or None,
            tool_registry=tool_registry,
        ),
        handles={"review_build", "audit_run"},
    )
    orchestrator.register_agent(
        WriterAgent(
            provider,
            artifact_service=services.artifact_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
        ),
        handles={"write_draft", "write_section"},
    )
    orchestrator.register_agent(
        StyleAgent(
            provider,
            artifact_service=services.artifact_service,
            model=config.provider_model or None,
            tool_registry=tool_registry,
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
    services = RuntimeServices(
        project_service=ProjectService(project_repository),
        task_service=TaskService(task_repository),
        claim_service=claim_service,
        run_service=run_service,
        freeze_service=FreezeService(),
        paper_card_service=PaperCardService(),
        gap_map_service=GapMapService(),
        approval_service=ApprovalService(),
        artifact_service=ArtifactService(),
        audit_service=AuditService(claim_service, run_service),
        tool_registry=build_tool_registry(),
        orchestrator=Orchestrator(TaskService(task_repository)),
    )
    services.orchestrator = build_orchestrator(config, services)
    return services
