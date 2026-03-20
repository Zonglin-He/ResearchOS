from pathlib import Path
from types import SimpleNamespace

from app.console.app import TerminalControlPlaneApp
from app.console.catalog import (
    available_dispatch_profile_choices,
    build_dispatch_profile,
    recommend_first_task_kind,
)
import app.console.app as console_app_module
from app.console.control_plane import ConsoleControlPlane, ProjectCreateInput, TaskCreateInput
from app.console.guide_agent import OnboardingGuideAgent
from app.db.repositories.in_memory_project_repository import InMemoryProjectRepository
from app.db.repositories.in_memory_task_repository import InMemoryTaskRepository
from app.providers.registry import ProviderRegistry
from app.roles import role_routing_policy_for_role
from app.routing.models import DispatchProfile, ProviderSpec
from app.routing.resolver import RoutingResolver
from app.schemas.task import TaskStatus
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


def test_console_catalog_exposes_gemini_3_profiles() -> None:
    choices = available_dispatch_profile_choices(
        DispatchProfile(
            provider=ProviderSpec(provider_name="claude", model="sonnet"),
            max_steps=12,
        )
    )

    labels = {choice.label for choice in choices}

    assert "Gemini 3.1 Pro Preview" in labels
    assert "Gemini 3 Flash Preview" in labels
    assert "Gemini 3.1 Flash-Lite Preview" in labels


def test_role_routing_prefers_explicit_gemini_3_models_for_non_claude_defaults() -> None:
    librarian = role_routing_policy_for_role("librarian")
    synthesizer = role_routing_policy_for_role("synthesizer")
    archivist = role_routing_policy_for_role("archivist")

    assert librarian.family_model_priority["gemini"] == [
        "gemini-3-flash-preview",
        "gemini-3.1-flash-lite-preview",
    ]
    assert synthesizer.family_model_priority["gemini"] == [
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
    ]
    assert archivist.family_model_priority["gemini"] == [
        "gemini-3.1-flash-lite-preview",
        "gemini-3-flash-preview",
    ]


def test_recommend_first_task_kind_matches_goal_shape() -> None:
    assert recommend_first_task_kind("survey the literature on retrieval").task_kind == "paper_ingest"
    assert recommend_first_task_kind("map the novelty gaps in this area").task_kind == "gap_mapping"
    assert recommend_first_task_kind("design the first experiment and baseline").task_kind == "build_spec"
    assert recommend_first_task_kind("write the initial paper draft").task_kind == "write_draft"


def test_terminal_console_guides_first_project_creation(monkeypatch, tmp_path: Path) -> None:
    control_plane = build_control_plane(tmp_path)
    app = TerminalControlPlaneApp(control_plane)

    prompts = iter(
        [
            "proj-1",
            "First Project",
            "Guided project",
            "active",
            "survey the literature on research systems",
            "research systems",
            "ResearchOS paper",
            "A compact summary.",
            "terminal workflows",
            "task-1",
            "survey the literature on research systems",
            "operator",
        ]
    )
    choices = iter(
        [
            "Inherit system default",
            "Inherit system default",
        ]
    )
    dispatched: list[str] = []
    confirms = iter([True, True, True, True])

    monkeypatch.setattr(console_app_module.Prompt, "ask", lambda *args, **kwargs: next(prompts))
    monkeypatch.setattr(
        console_app_module.Confirm,
        "ask",
        lambda *args, **kwargs: next(confirms),
    )
    monkeypatch.setattr(app, "_choose", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(
        control_plane,
        "dispatch_task",
        lambda task_id, run_async=False: dispatched.append(task_id)
        or SimpleNamespace(
            task=SimpleNamespace(task_id=task_id, status=SimpleNamespace(value="succeeded")),
            result=SimpleNamespace(status="success", routing=None),
        ),
    )

    app._maybe_run_first_project_guide()

    projects = control_plane.list_projects()
    tasks = control_plane.list_tasks(project_id="proj-1")

    assert len(projects) == 1
    assert projects[0].project_id == "proj-1"
    assert len(tasks) == 1
    assert tasks[0].task_id == "task-1"
    assert tasks[0].kind == "paper_ingest"
    assert tasks[0].goal == "survey the literature on research systems"
    assert tasks[0].input_payload["source_summary"]["title"] == "ResearchOS paper"
    assert dispatched == ["task-1"]


def test_onboarding_guide_agent_recommends_next_step_from_project_state(tmp_path: Path) -> None:
    control_plane = build_control_plane(tmp_path)
    guide = OnboardingGuideAgent()
    project = control_plane.create_project(
        ProjectCreateInput(
            project_id="proj-1",
            name="Guide Project",
            description="Study retrieval robustness",
        )
    )

    empty_plan = guide.build_project_plan(project, [])
    assert empty_plan.recommended_task_kind == "paper_ingest"
    assert empty_plan.expected_artifact == "paper_card"
    assert empty_plan.likely_next_task_kind == "gap_mapping"

    control_plane.create_task(
        TaskCreateInput(
            task_id="t-ingest",
            project_id="proj-1",
            kind="paper_ingest",
            goal="Read sources",
            owner="tester",
            input_payload={"topic": "retrieval"},
        )
    )
    task = control_plane.task_service.get_task("t-ingest")
    assert task is not None
    control_plane.task_service.update_status(task.task_id, TaskStatus.RUNNING)
    control_plane.task_service.update_status(task.task_id, TaskStatus.SUCCEEDED)

    plan = guide.build_project_plan(project, control_plane.list_tasks(project_id="proj-1"))
    assert plan.recommended_task_kind == "gap_mapping"
    assert "next useful step" in plan.recommendation_reason
    assert plan.expected_artifact == "gap_map"
    assert plan.likely_next_task_kind == "build_spec"


def test_first_project_guide_explains_reason_artifact_and_follow_up() -> None:
    guide = OnboardingGuideAgent()

    plan = guide.build_first_project_plan("design the first experiment and baseline")

    assert plan.recommended_task_kind == "build_spec"
    assert "safest first step" in plan.recommendation_reason
    assert plan.expected_artifact == "hypothesis_set / experiment_spec"
    assert plan.likely_next_task_kind == "implement_experiment"


def test_project_menu_can_create_recommended_guided_task(monkeypatch, tmp_path: Path) -> None:
    control_plane = build_control_plane(tmp_path)
    control_plane.create_project(
        ProjectCreateInput(
            project_id="proj-2",
            name="Project Guided Flow",
            description="Write the first draft",
        )
    )
    app = TerminalControlPlaneApp(control_plane)

    prompts = iter(
        [
            "",
            "task-guide-1",
            "Write the first draft",
            "operator",
        ]
    )
    choices = iter(
        [
            "proj-2 | Project Guided Flow",
            "Inherit system default",
        ]
    )
    confirms = iter([True])

    monkeypatch.setattr(console_app_module.Prompt, "ask", lambda *args, **kwargs: next(prompts))
    monkeypatch.setattr(console_app_module.Confirm, "ask", lambda *args, **kwargs: next(confirms))
    monkeypatch.setattr(app, "_choose", lambda *args, **kwargs: next(choices))

    app._guide_project_flow()

    tasks = control_plane.list_tasks(project_id="proj-2")
    assert len(tasks) == 1
    assert tasks[0].kind == "write_draft"
    assert tasks[0].goal == "Write the first draft"
