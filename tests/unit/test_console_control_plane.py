from pathlib import Path
from types import SimpleNamespace

from app.console.catalog import available_dispatch_profile_choices, build_dispatch_profile
from app.console.control_plane import ConsoleControlPlane, ProjectCreateInput, TaskCreateInput
from app.db.repositories.in_memory_project_repository import InMemoryProjectRepository
from app.db.repositories.in_memory_task_repository import InMemoryTaskRepository
from app.providers.registry import ProviderRegistry
from app.routing.models import DispatchProfile, ProviderSpec
from app.routing.resolver import RoutingResolver
from app.services.approval_service import ApprovalService
from app.services.artifact_service import ArtifactService
from app.services.claim_service import ClaimService
from app.services.freeze_service import FreezeService
from app.services.gap_map_service import GapMapService
from app.services.paper_card_service import PaperCardService
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.services.task_service import TaskService


class DummyOrchestrator:
    async def dispatch(self, task_id: str):
        raise NotImplementedError


def build_control_plane(tmp_path: Path) -> ConsoleControlPlane:
    provider_registry = ProviderRegistry()
    provider_registry.register("claude", lambda: object())
    provider_registry.register("codex", lambda: object())
    provider_registry.register("gemini", lambda: object())
    return ConsoleControlPlane(
        project_service=ProjectService(InMemoryProjectRepository()),
        task_service=TaskService(InMemoryTaskRepository()),
        approval_service=ApprovalService(tmp_path / "approvals.jsonl"),
        run_service=RunService(tmp_path / "runs.jsonl"),
        artifact_service=ArtifactService(tmp_path / "artifacts.jsonl"),
        claim_service=ClaimService(tmp_path / "claims.jsonl"),
        paper_card_service=PaperCardService(tmp_path / "paper_cards.jsonl"),
        gap_map_service=GapMapService(tmp_path / "gap_maps.jsonl"),
        freeze_service=FreezeService(tmp_path / "freezes"),
        orchestrator=DummyOrchestrator(),
        routing_resolver=RoutingResolver(
            DispatchProfile(
                provider=ProviderSpec(provider_name="claude", model="sonnet"),
                max_steps=12,
            )
        ),
        provider_registry=provider_registry,
    )


def test_console_control_plane_creates_project_and_task_with_dispatch_profile(tmp_path: Path) -> None:
    control_plane = build_control_plane(tmp_path)
    dispatch_profile = build_dispatch_profile("codex", "gpt-5.4", max_steps=18)

    project = control_plane.create_project(
        ProjectCreateInput(
            project_id="p1",
            name="ResearchOS",
            description="console project",
            dispatch_profile=dispatch_profile,
        )
    )
    task = control_plane.create_task(
        TaskCreateInput(
            task_id="t1",
            project_id="p1",
            kind="paper_ingest",
            goal="Read one source",
            owner="tester",
            input_payload={"topic": "agents"},
            dispatch_profile=dispatch_profile,
        )
    )

    assert project.dispatch_profile is not None
    assert project.dispatch_profile.provider is not None
    assert project.dispatch_profile.provider.provider_name == "codex"
    assert task.dispatch_profile is not None
    assert task.dispatch_profile.provider is not None
    assert task.dispatch_profile.max_steps == 18


def test_console_control_plane_builds_source_summary_payload() -> None:
    payload = ConsoleControlPlane.build_task_input_payload(
        kind="paper_ingest",
        topic="research agents",
        source_title="ResearchOS",
        source_abstract="A workflow runtime.",
        source_setting="research systems",
    )

    assert payload["topic"] == "research agents"
    assert payload["source_summary"]["title"] == "ResearchOS"
    assert payload["source_summary"]["setting"] == "research systems"


def test_console_catalog_exposes_inherit_and_known_profiles() -> None:
    choices = available_dispatch_profile_choices(
        DispatchProfile(
            provider=ProviderSpec(provider_name="claude", model="sonnet"),
            max_steps=12,
        )
    )

    assert choices[0].dispatch_profile is None
    assert choices[0].label == "Inherit system default"
    assert any(choice.label == "Codex GPT-5.4" for choice in choices)
