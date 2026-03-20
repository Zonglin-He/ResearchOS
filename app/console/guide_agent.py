from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.console.catalog import FirstTaskRecommendation, recommend_first_task_kind
from app.providers.registry import ProviderRegistry
from app.roles import WorkflowRole, role_routing_policy_for_role
from app.routing.models import AgentRoutingPolicy, ResolvedDispatch
from app.routing.provider_router import ProviderInvocationService
from app.routing.resolver import RoutingResolver
from app.schemas.project import Project
from app.schemas.task import Task, TaskStatus


GUIDE_TASK_KINDS = (
    "paper_ingest",
    "repo_ingest",
    "read_source",
    "gap_mapping",
    "map_gaps",
    "build_spec",
    "implement_experiment",
    "reproduce_baseline",
    "review_build",
    "audit_run",
    "verify_evidence",
    "verify_results",
    "write_draft",
    "write_section",
    "style_pass",
    "polish_draft",
    "archive_research",
    "archive_run",
    "record_lessons",
)


@dataclass(frozen=True)
class GuideStep:
    title: str
    status: str
    detail: str


@dataclass(frozen=True)
class GuidePlan:
    prompt_id: str
    headline: str
    assistant_message: str
    summary: str
    follow_up_prompt: str = ""
    recommended_task_kind: str | None = None
    recommendation_reason: str = ""
    suggested_goal: str = ""
    suggested_project_name: str = ""
    suggested_project_description: str = ""
    expected_artifact: str = ""
    likely_next_task_kind: str | None = None
    routing_provider_name: str | None = None
    routing_model: str | None = None
    fallback_reason: str | None = None
    steps: tuple[GuideStep, ...] = field(default_factory=tuple)


class OnboardingGuideAgent:
    prompt_id = "console-onboarding-guide"
    prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "console" / "onboarding_guide.md"

    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry | None = None,
        routing_resolver: RoutingResolver | None = None,
        provider_invocation_service: ProviderInvocationService | None = None,
    ) -> None:
        self.provider_registry = provider_registry
        self.routing_resolver = routing_resolver
        self.provider_invocation_service = provider_invocation_service
        self.routing_policy = AgentRoutingPolicy(
            agent_name="console_guide_agent",
            default_role_policy=role_routing_policy_for_role(WorkflowRole.SCOPER),
            metadata={"surface": "console"},
        )

    def prompt_text(self) -> str:
        return self.prompt_path.read_text(encoding="utf-8").strip()

    def opening_message(self, *, has_projects: bool) -> str:
        if has_projects:
            return (
                "I am the ResearchOS guide agent. Tell me which project you want to move forward, "
                "and I will recommend one bounded next step, the artifact it should produce, and what usually follows."
            )
        return (
            "I am the ResearchOS guide agent. Tell me your research goal in one sentence. "
            "I will recommend the safest first task, explain why it comes first, and guide you through creating it."
        )

    def build_first_project_plan(self, research_goal: str) -> GuidePlan:
        recommendation = recommend_first_task_kind(research_goal)
        fallback_plan = GuidePlan(
            prompt_id=self.prompt_id,
            headline="First Project Guide",
            assistant_message=(
                f"I recommend starting with {recommendation.task_kind}. "
                f"{recommendation.rationale} That first task should create a durable artifact before you go deeper."
            ),
            summary=(
                "Start by creating a project container, choose a default routing profile, "
                "then create one bounded first task and dispatch it."
            ),
            follow_up_prompt="I can suggest a project container next. If you do not have a name yet, I will suggest one.",
            recommended_task_kind=recommendation.task_kind,
            recommendation_reason=recommendation.rationale,
            suggested_goal=research_goal,
            suggested_project_name=self._suggest_project_name(research_goal),
            suggested_project_description=self._suggest_project_description(research_goal),
            expected_artifact=self._expected_artifact_for_task_kind(recommendation.task_kind),
            likely_next_task_kind=self._likely_follow_up_for_task_kind(recommendation.task_kind),
            steps=(
                GuideStep("Create the project", "next", "Define the project container and default routing."),
                GuideStep(
                    "Create the first task",
                    "next",
                    f"Recommended task kind: {recommendation.task_kind}.",
                ),
                GuideStep("Dispatch the task", "later", "Run the first task to produce the first artifact."),
                GuideStep(
                    "Inspect outputs",
                    "later",
                    "Check tasks, artifacts, paper cards, or gap maps before moving to the next stage.",
                ),
            ),
        )
        return self._generate_agent_plan(
            mode="first_project",
            research_goal=research_goal,
            project=None,
            tasks=[],
            fallback_plan=fallback_plan,
        )

    def build_project_plan(self, project: Project, tasks: list[Task]) -> GuidePlan:
        recommendation = self._recommend_from_project_state(project, tasks)
        fallback_plan = GuidePlan(
            prompt_id=self.prompt_id,
            headline=f"Project Guide: {project.name}",
            assistant_message=(
                f"I reviewed the current project state. The next bounded step should be {recommendation.task_kind}. "
                f"{recommendation.rationale}"
            ),
            summary=self._summarize_project_state(tasks),
            follow_up_prompt="If you want, I can help you create that next task now.",
            recommended_task_kind=recommendation.task_kind,
            recommendation_reason=recommendation.rationale,
            suggested_goal=self._goal_hint(project, recommendation.task_kind),
            suggested_project_name=project.name,
            suggested_project_description=project.description,
            expected_artifact=self._expected_artifact_for_task_kind(recommendation.task_kind),
            likely_next_task_kind=self._likely_follow_up_for_task_kind(recommendation.task_kind),
            steps=self._build_project_steps(tasks, recommendation.task_kind),
        )
        return self._generate_agent_plan(
            mode="existing_project",
            research_goal=project.description or project.name,
            project=project,
            tasks=tasks,
            fallback_plan=fallback_plan,
        )

    def _generate_agent_plan(
        self,
        *,
        mode: str,
        research_goal: str,
        project: Project | None,
        tasks: list[Task],
        fallback_plan: GuidePlan,
    ) -> GuidePlan:
        if (
            self.provider_registry is None
            or self.routing_resolver is None
            or self.provider_invocation_service is None
        ):
            return fallback_plan
        try:
            return asyncio.run(
                self._generate_agent_plan_async(
                    mode=mode,
                    research_goal=research_goal,
                    project=project,
                    tasks=tasks,
                    fallback_plan=fallback_plan,
                )
            )
        except Exception:
            return fallback_plan

    async def _generate_agent_plan_async(
        self,
        *,
        mode: str,
        research_goal: str,
        project: Project | None,
        tasks: list[Task],
        fallback_plan: GuidePlan,
    ) -> GuidePlan:
        routing = self._resolve_routing(mode=mode, research_goal=research_goal, project=project)
        payload = {
            "guide_request": {
                "mode": mode,
                "research_goal": research_goal,
                "project": None
                if project is None
                else {
                    "project_id": project.project_id,
                    "name": project.name,
                    "description": project.description,
                    "status": project.status,
                },
                "task_summary": self._task_summary(tasks),
                "heuristic_recommendation": {
                    "recommended_task_kind": fallback_plan.recommended_task_kind,
                    "recommendation_reason": fallback_plan.recommendation_reason,
                    "expected_artifact": fallback_plan.expected_artifact,
                    "likely_next_task_kind": fallback_plan.likely_next_task_kind,
                    "suggested_project_name": fallback_plan.suggested_project_name,
                    "suggested_project_description": fallback_plan.suggested_project_description,
                    "suggested_task_goal": fallback_plan.suggested_goal,
                },
            }
        }
        output, final_routing = await self.provider_invocation_service.generate(
            routing=routing,
            system_prompt=self.prompt_text(),
            user_input=self._json_payload(payload),
            tools=None,
            response_schema=self._response_schema(),
        )
        return self._merge_provider_output(
            fallback_plan=fallback_plan,
            output=output,
            final_routing=final_routing,
        )

    def _resolve_routing(
        self,
        *,
        mode: str,
        research_goal: str,
        project: Project | None,
    ) -> ResolvedDispatch:
        if self.routing_resolver is None:
            raise RuntimeError("Guide agent routing is not configured.")
        guide_task = Task(
            task_id=f"console-guide-{mode}",
            project_id=project.project_id if project is not None else "console",
            kind="console_guide",
            goal=research_goal or "Guide the operator through the next ResearchOS step.",
            input_payload={"guide_request": {"mode": mode}},
            owner="console_guide_agent",
        )
        return self.routing_resolver.resolve(
            task=guide_task,
            project=project,
            agent_policy=self.routing_policy,
        )

    def _merge_provider_output(
        self,
        *,
        fallback_plan: GuidePlan,
        output: dict[str, Any],
        final_routing: ResolvedDispatch,
    ) -> GuidePlan:
        recommended_task_kind = self._normalize_task_kind(
            output.get("recommended_task_kind"),
            fallback_plan.recommended_task_kind,
        )
        expected_artifact = self._string_or_fallback(
            output.get("expected_artifact"),
            fallback_plan.expected_artifact,
        )
        likely_next_task_kind = self._normalize_task_kind(
            output.get("likely_next_task_kind"),
            fallback_plan.likely_next_task_kind,
            allow_empty=True,
        )
        return GuidePlan(
            prompt_id=fallback_plan.prompt_id,
            headline=fallback_plan.headline,
            assistant_message=self._string_or_fallback(
                output.get("assistant_message"),
                fallback_plan.assistant_message,
            ),
            summary=self._string_or_fallback(output.get("summary"), fallback_plan.summary),
            follow_up_prompt=self._string_or_fallback(
                output.get("follow_up_prompt"),
                fallback_plan.follow_up_prompt,
            ),
            recommended_task_kind=recommended_task_kind,
            recommendation_reason=self._string_or_fallback(
                output.get("recommendation_reason"),
                fallback_plan.recommendation_reason,
            ),
            suggested_goal=self._string_or_fallback(
                output.get("suggested_task_goal"),
                fallback_plan.suggested_goal,
            ),
            suggested_project_name=self._string_or_fallback(
                output.get("suggested_project_name"),
                fallback_plan.suggested_project_name,
            ),
            suggested_project_description=self._string_or_fallback(
                output.get("suggested_project_description"),
                fallback_plan.suggested_project_description,
            ),
            expected_artifact=expected_artifact,
            likely_next_task_kind=likely_next_task_kind,
            routing_provider_name=final_routing.provider_name,
            routing_model=final_routing.model,
            fallback_reason=final_routing.fallback_reason,
            steps=fallback_plan.steps,
        )

    def _recommend_from_project_state(
        self,
        project: Project,
        tasks: list[Task],
    ) -> FirstTaskRecommendation:
        completed_kinds = {
            task.kind
            for task in tasks
            if task.status in {TaskStatus.SUCCEEDED, TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL}
        }
        if not tasks:
            base_goal = project.description or project.name
            return recommend_first_task_kind(base_goal)
        if not completed_kinds.intersection({"paper_ingest", "repo_ingest", "read_source"}):
            return FirstTaskRecommendation(
                "paper_ingest",
                "This project has no completed ingestion task yet, so start by normalizing source evidence into paper cards.",
            )
        if not completed_kinds.intersection({"gap_mapping", "map_gaps"}):
            return FirstTaskRecommendation(
                "gap_mapping",
                "You already have source-ingestion work. The next useful step is to cluster evidence into a gap map.",
            )
        if not completed_kinds.intersection({"build_spec", "implement_experiment", "reproduce_baseline"}):
            return FirstTaskRecommendation(
                "build_spec",
                "You have evidence and gap structure. The next step is to turn that into an experiment spec.",
            )
        if not completed_kinds.intersection({"review_build", "audit_run", "verify_evidence", "verify_results"}):
            return FirstTaskRecommendation(
                "audit_run",
                "Execution work exists, but there is no completed review or verification pass yet.",
            )
        if not completed_kinds.intersection({"write_draft", "write_section"}):
            return FirstTaskRecommendation(
                "write_draft",
                "Research outputs exist. The next step is to turn approved evidence into a draft.",
            )
        if not completed_kinds.intersection({"style_pass", "polish_draft"}):
            return FirstTaskRecommendation(
                "style_pass",
                "A draft exists. A style pass is the cleanest next step before export or submission.",
            )
        return FirstTaskRecommendation(
            "archive_research",
            "The core project loop is already populated. Capture lessons and provenance before starting the next cycle.",
        )

    @staticmethod
    def _goal_hint(project: Project, task_kind: str) -> str:
        base = project.description or project.name
        if task_kind == "gap_mapping":
            return f"Map the main research gaps for {base}"
        if task_kind == "build_spec":
            return f"Design the first experiment for {base}"
        if task_kind == "audit_run":
            return f"Review the latest run outputs for {base}"
        if task_kind == "write_draft":
            return f"Draft the first section for {base}"
        if task_kind == "style_pass":
            return f"Polish the current draft for {base}"
        if task_kind == "archive_research":
            return f"Archive lessons and provenance for {base}"
        return base

    @staticmethod
    def _summarize_project_state(tasks: list[Task]) -> str:
        if not tasks:
            return "This project has no tasks yet. Start with one bounded task that creates the first durable artifact."
        total = len(tasks)
        succeeded = sum(1 for task in tasks if task.status == TaskStatus.SUCCEEDED)
        running = sum(1 for task in tasks if task.status == TaskStatus.RUNNING)
        waiting = sum(1 for task in tasks if task.status == TaskStatus.WAITING_APPROVAL)
        return (
            f"This project currently has {total} task(s): "
            f"{succeeded} succeeded, {running} running, {waiting} waiting for approval."
        )

    @staticmethod
    def _build_project_steps(tasks: list[Task], recommended_task_kind: str) -> tuple[GuideStep, ...]:
        has_tasks = bool(tasks)
        completed = {task.kind for task in tasks if task.status == TaskStatus.SUCCEEDED}
        return (
            GuideStep(
                "Project container",
                "done" if has_tasks else "next",
                "The project exists. Keep new work attached to this project instead of starting a new container.",
            ),
            GuideStep(
                "Evidence collection",
                "done" if completed.intersection({"paper_ingest", "repo_ingest", "read_source"}) else "next",
                "Create or verify source-ingestion work before synthesis.",
            ),
            GuideStep(
                "Knowledge synthesis",
                "done" if completed.intersection({"gap_mapping", "map_gaps"}) else ("next" if recommended_task_kind == "gap_mapping" else "later"),
                "Build a gap map before hypothesis and experiment planning.",
            ),
            GuideStep(
                "Experiment design/execution",
                "done" if completed.intersection({"build_spec", "implement_experiment", "reproduce_baseline"}) else ("next" if recommended_task_kind in {"build_spec", "implement_experiment"} else "later"),
                "Turn evidence into a runnable spec and then execute it.",
            ),
            GuideStep(
                "Review, verify, publish, archive",
                "next" if recommended_task_kind in {"audit_run", "write_draft", "style_pass", "archive_research"} else "later",
                "Review and verification should happen before polished publishing and archival.",
            ),
        )

    @staticmethod
    def _expected_artifact_for_task_kind(task_kind: str) -> str:
        mapping = {
            "paper_ingest": "paper_card",
            "repo_ingest": "paper_card",
            "read_source": "paper_card",
            "gap_mapping": "gap_map",
            "map_gaps": "gap_map",
            "build_spec": "hypothesis_set / experiment_spec",
            "implement_experiment": "run_manifest",
            "reproduce_baseline": "run_manifest",
            "audit_run": "review_report",
            "review_build": "review_report",
            "verify_evidence": "verification_report",
            "verify_results": "verification_report",
            "write_draft": "paper_draft",
            "write_section": "section_draft",
            "style_pass": "styled draft artifact",
            "polish_draft": "styled draft artifact",
            "archive_research": "archive_entry",
            "archive_run": "archive_entry",
            "record_lessons": "archive_entry / lesson linkage",
        }
        return mapping.get(task_kind, "workflow artifact")

    @staticmethod
    def _likely_follow_up_for_task_kind(task_kind: str) -> str | None:
        mapping = {
            "paper_ingest": "gap_mapping",
            "repo_ingest": "gap_mapping",
            "read_source": "gap_mapping",
            "gap_mapping": "build_spec",
            "build_spec": "implement_experiment",
            "implement_experiment": "audit_run",
            "reproduce_baseline": "audit_run",
            "audit_run": "write_draft",
            "review_build": "verify_evidence",
            "verify_evidence": "write_draft",
            "verify_results": "write_draft",
            "write_draft": "style_pass",
            "write_section": "style_pass",
            "style_pass": "archive_research",
            "polish_draft": "archive_research",
        }
        return mapping.get(task_kind)

    @staticmethod
    def _task_summary(tasks: list[Task]) -> dict[str, Any]:
        return {
            "count": len(tasks),
            "by_status": {
                status.value: sum(1 for task in tasks if task.status == status)
                for status in TaskStatus
            },
            "kinds": [task.kind for task in tasks],
        }

    @staticmethod
    def _suggest_project_name(research_goal: str) -> str:
        tokens = [token for token in research_goal.replace("-", " ").split() if token]
        if not tokens:
            return "ResearchOS Project"
        title = " ".join(tokens[:4]).strip()
        return title.title()

    @staticmethod
    def _suggest_project_description(research_goal: str) -> str:
        if not research_goal.strip():
            return "Guided ResearchOS project."
        return research_goal.strip()

    @staticmethod
    def _response_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "assistant_message": {"type": "string"},
                "summary": {"type": "string"},
                "follow_up_prompt": {"type": "string"},
                "recommended_task_kind": {"type": "string", "enum": list(GUIDE_TASK_KINDS)},
                "recommendation_reason": {"type": "string"},
                "expected_artifact": {"type": "string"},
                "likely_next_task_kind": {
                    "type": "string",
                    "enum": list(GUIDE_TASK_KINDS),
                },
                "suggested_project_name": {"type": "string"},
                "suggested_project_description": {"type": "string"},
                "suggested_task_goal": {"type": "string"},
            },
            "required": [
                "assistant_message",
                "recommended_task_kind",
                "recommendation_reason",
                "expected_artifact",
            ],
        }

    @staticmethod
    def _json_payload(payload: dict[str, Any]) -> str:
        import json

        return json.dumps(payload, ensure_ascii=False, default=str)

    @staticmethod
    def _string_or_fallback(value: Any, fallback: str) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return fallback

    @staticmethod
    def _normalize_task_kind(
        value: Any,
        fallback: str | None,
        *,
        allow_empty: bool = False,
    ) -> str | None:
        if isinstance(value, str) and value in GUIDE_TASK_KINDS:
            return value
        if allow_empty:
            return fallback
        return fallback
