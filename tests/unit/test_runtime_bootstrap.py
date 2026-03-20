from pathlib import Path

from app.bootstrap import build_runtime_services
from app.core.config import AppConfig
from app.core.paths import WorkspacePaths
from app.schemas.claim import Claim
from app.schemas.project import Project
from app.schemas.task import Task


def test_runtime_bootstrap_uses_sqlite_when_database_url_is_empty(tmp_path: Path) -> None:
    config = AppConfig(db_path=str(tmp_path / "researchos.db"))
    services = build_runtime_services(config)

    services.project_service.create_project(
        Project(
            project_id="p1",
            name="ResearchOS",
            description="Bootstrap project",
            status="active",
        )
    )
    services.task_service.create_task(
        Task(
            task_id="t1",
            project_id="p1",
            kind="paper_ingest",
            goal="Ingest paper",
            input_payload={},
            owner="gabriel",
        )
    )

    assert services.project_service.get_project("p1") is not None
    assert services.task_service.get_task("t1") is not None
    assert services.tool_registry.get("filesystem").name == "filesystem"
    assert services.experiment_manager is not None
    assert services.lessons_service is not None
    assert services.verification_service is not None
    assert services.provider_health_service is not None
    assert services.provider_invocation_service is not None
    assert services.orchestrator is not None
    assert services.orchestrator._kind_to_agent["paper_ingest"] == "reader_agent"
    assert services.orchestrator._kind_to_agent["gap_mapping"] == "mapper_agent"
    assert services.orchestrator._kind_to_agent["implement_experiment"] == "builder_agent"
    assert services.orchestrator._kind_to_agent["review_build"] == "reviewer_agent"
    assert services.orchestrator._kind_to_agent["write_draft"] == "writer_agent"
    assert services.orchestrator._kind_to_agent["style_pass"] == "style_agent"
    assert services.orchestrator._kind_to_agent["analyze_results"] == "analyst_agent"
    assert services.orchestrator._kind_to_agent["verify_evidence"] == "verifier_agent"
    assert services.orchestrator._kind_to_agent["archive_research"] == "archivist_agent"
    reader_agent = services.orchestrator._agents["reader_agent"]
    reader_role_spec = reader_agent.role_binding.resolve_role_spec("paper_ingest")
    assert reader_role_spec is not None
    assert reader_role_spec.role_id.value == "librarian"
    assert services.role_prompt_registry.require_for_role("librarian").path.exists()
    assert services.role_skill_registry.list_for_role("librarian")
    assert reader_agent.role_prompt_registry is services.role_prompt_registry
    assert reader_agent.role_skill_registry is services.role_skill_registry


def test_runtime_bootstrap_resolves_workspace_backed_registry_paths(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    config = AppConfig(
        db_path=str(tmp_path / "researchos.db"),
        workspace_root=str(workspace_root),
        provider_name="local",
    )

    services = build_runtime_services(config)
    paths = WorkspacePaths.from_root(workspace_root)

    services.claim_service.register_claim(
        Claim(
            claim_id="claim-1",
            text="Local workspace-backed claim",
            claim_type="result",
        )
    )

    assert services.claim_service.registry_path == paths.registry_file("claims.jsonl")
    assert services.run_service.registry_path == paths.registry_file("runs.jsonl")
    assert services.freeze_service.freeze_dir == paths.freezes_dir
    assert services.artifact_service.registry_path == paths.registry_file("artifacts.jsonl")
    assert services.lessons_service.registry_path == paths.registry_file("lessons.jsonl")
    assert services.verification_service.registry_path == paths.registry_file("verifications.jsonl")
    assert services.experiment_manager.registry.base_dir == paths.experiments_dir
    assert paths.registry_file("claims.jsonl").exists()
