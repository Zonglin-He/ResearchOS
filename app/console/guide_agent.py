from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.console.catalog import FirstTaskRecommendation, recommend_first_task_kind
from app.schemas.project import Project
from app.schemas.task import Task, TaskStatus


@dataclass(frozen=True)
class GuideStep:
    title: str
    status: str
    detail: str


@dataclass(frozen=True)
class GuidePlan:
    prompt_id: str
    headline: str
    summary: str
    recommended_task_kind: str | None = None
    recommendation_reason: str = ""
    suggested_goal: str = ""
    expected_artifact: str = ""
    likely_next_task_kind: str | None = None
    steps: tuple[GuideStep, ...] = field(default_factory=tuple)


class OnboardingGuideAgent:
    prompt_id = "console-onboarding-guide"
    prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "console" / "onboarding_guide.md"

    def prompt_text(self) -> str:
        return self.prompt_path.read_text(encoding="utf-8").strip()

    def build_first_project_plan(self, research_goal: str) -> GuidePlan:
        recommendation = recommend_first_task_kind(research_goal)
        return GuidePlan(
            prompt_id=self.prompt_id,
            headline="First Project Guide",
            summary=(
                "Start by creating a project container, choose a default routing profile, "
                "then create one bounded first task and dispatch it."
            ),
            recommended_task_kind=recommendation.task_kind,
            recommendation_reason=recommendation.rationale,
            suggested_goal=research_goal,
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

    def build_project_plan(self, project: Project, tasks: list[Task]) -> GuidePlan:
        recommendation = self._recommend_from_project_state(project, tasks)
        return GuidePlan(
            prompt_id=self.prompt_id,
            headline=f"Project Guide: {project.name}",
            summary=self._summarize_project_state(tasks),
            recommended_task_kind=recommendation.task_kind,
            recommendation_reason=recommendation.rationale,
            suggested_goal=self._goal_hint(project, recommendation.task_kind),
            expected_artifact=self._expected_artifact_for_task_kind(recommendation.task_kind),
            likely_next_task_kind=self._likely_follow_up_for_task_kind(recommendation.task_kind),
            steps=self._build_project_steps(tasks, recommendation.task_kind),
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
