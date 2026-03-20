from __future__ import annotations

import time
from typing import Sequence

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt

from app.console.catalog import (
    DispatchProfileChoice,
    available_dispatch_profile_choices,
    available_model_choices,
    build_dispatch_profile,
    recommend_first_task_kind,
)
from app.console.control_plane import (
    ApprovalCreateInput,
    ConsoleControlPlane,
    ProjectCreateInput,
    TaskCreateInput,
)
from app.console.render import (
    build_approvals_table,
    build_artifacts_table,
    build_gap_maps_table,
    build_paper_cards_table,
    build_projects_table,
    build_runs_table,
    build_tasks_table,
)


TASK_KIND_OPTIONS = [
    "paper_ingest",
    "repo_ingest",
    "read_source",
    "gap_mapping",
    "build_spec",
    "implement_experiment",
    "reproduce_baseline",
    "review_build",
    "audit_run",
    "write_draft",
    "write_section",
    "style_pass",
    "polish_draft",
]


class TerminalControlPlaneApp:
    def __init__(self, control_plane: ConsoleControlPlane, *, refresh_interval: float = 2.0) -> None:
        self.control_plane = control_plane
        self.console = Console()
        self.refresh_interval = refresh_interval

    def run(self) -> int:
        self.console.print(
            Panel.fit(
                "ResearchOS Console\n"
                "Interactive terminal control plane for projects, tasks, approvals, runs, and registries.",
                title="ResearchOS",
            )
        )
        self._maybe_run_first_project_guide()
        while True:
            self._print_system_routing()
            choice = self._choose(
                "Main Menu",
                [
                    "Projects",
                    "Tasks",
                    "Approvals",
                    "Runs",
                    "Registries",
                    "Exit",
                ],
            )
            if choice == "Projects":
                self._projects_menu()
            elif choice == "Tasks":
                self._tasks_menu()
            elif choice == "Approvals":
                self._approvals_menu()
            elif choice == "Runs":
                self._runs_menu()
            elif choice == "Registries":
                self._registries_menu()
            else:
                return 0

    def _maybe_run_first_project_guide(self) -> None:
        if self.control_plane.has_projects():
            return
        self.console.print(
            Panel.fit(
                "No projects found.\n"
                "ResearchOS Guide will help you create your first project, choose a routing profile, "
                "and optionally create and dispatch the first task.",
                title="First Project Guide",
            )
        )
        if not Confirm.ask("Start guided setup now?", default=True):
            return

        project = self._run_guided_project_creation()
        self.console.print(f"[green]Created project[/green] {project.project_id}")

        if not Confirm.ask("Create the first task now?", default=True):
            return

        task = self._run_guided_first_task(project.project_id)
        self.console.print(f"[green]Created task[/green] {task.task_id}")

        if not Confirm.ask("Dispatch this task now?", default=True):
            return

        result = self.control_plane.dispatch_task(task.task_id, run_async=False)
        self.console.print(
            f"[green]Dispatched[/green] {result.task.task_id} -> "
            f"{result.task.status.value} ({result.result.status})"
        )
        if result.result.routing is not None:
            self.console.print(
                f"Routing: {result.result.routing.provider_name} / "
                f"{result.result.routing.model or '<default>'}"
            )

    def _run_guided_project_creation(self):
        self.console.print("[bold]Guide[/bold]: let's create a project container first.")
        data = ProjectCreateInput(
            project_id=Prompt.ask("Project ID"),
            name=Prompt.ask("Project name"),
            description=Prompt.ask("Short description"),
            status=Prompt.ask("Status", default="active"),
            dispatch_profile=self._select_dispatch_profile(),
        )
        return self.control_plane.create_project(data)

    def _run_guided_first_task(self, project_id: str):
        research_goal = Prompt.ask("Primary research goal", default="")
        recommendation = recommend_first_task_kind(research_goal)
        self.console.print(
            "[bold]Guide[/bold]: recommended first task kind -> "
            f"[cyan]{recommendation.task_kind}[/cyan]\n{recommendation.rationale}"
        )
        if Confirm.ask("Use the recommended first task kind?", default=True):
            kind = recommendation.task_kind
        else:
            kind = self._choose(
                "Choose the first task kind",
                [
                    "paper_ingest",
                    "gap_mapping",
                    "build_spec",
                    "write_draft",
                ],
            )
        topic = Prompt.ask("Topic", default="")
        source_title = ""
        source_abstract = ""
        source_setting = ""
        if kind in {"paper_ingest", "repo_ingest", "read_source"}:
            source_title = Prompt.ask("Source title", default="")
            source_abstract = Prompt.ask("Source abstract", default="")
            source_setting = Prompt.ask("Source setting", default="")

        return self.control_plane.create_task(
            TaskCreateInput(
                task_id=Prompt.ask("Task ID"),
                project_id=project_id,
                kind=kind,
                goal=Prompt.ask("Goal", default=research_goal),
                owner=Prompt.ask("Owner", default="operator"),
                input_payload=self.control_plane.build_task_input_payload(
                    kind=kind,
                    topic=topic,
                    source_title=source_title,
                    source_abstract=source_abstract,
                    source_setting=source_setting,
                ),
                assigned_agent=None,
                dispatch_profile=self._select_dispatch_profile(),
            )
        )

    def _print_system_routing(self) -> None:
        profile = self.control_plane.system_dispatch_profile()
        provider_name = profile.provider.provider_name if profile.provider is not None else "-"
        model = profile.provider.model if profile.provider is not None and profile.provider.model else "<default>"
        self.console.print(f"[bold]System routing[/bold]: {provider_name} / {model}")

    def _projects_menu(self) -> None:
        choice = self._choose("Projects", ["List projects", "Create project", "Back"])
        if choice == "List projects":
            self.console.print(build_projects_table(self.control_plane.list_projects()))
        elif choice == "Create project":
            data = ProjectCreateInput(
                project_id=Prompt.ask("Project ID"),
                name=Prompt.ask("Project name"),
                description=Prompt.ask("Description"),
                status=Prompt.ask("Status", default="active"),
                dispatch_profile=self._select_dispatch_profile(),
            )
            project = self.control_plane.create_project(data)
            self.console.print(f"[green]Created project[/green] {project.project_id}")

    def _tasks_menu(self) -> None:
        choice = self._choose(
            "Tasks",
            [
                "List tasks",
                "Create task",
                "Dispatch task",
                "Watch tasks",
                "Retry task",
                "Cancel task",
                "Back",
            ],
        )
        if choice == "List tasks":
            self.console.print(build_tasks_table(self.control_plane.list_tasks()))
        elif choice == "Create task":
            self._create_task_flow()
        elif choice == "Dispatch task":
            self._dispatch_task_flow()
        elif choice == "Watch tasks":
            self._watch_tasks()
        elif choice == "Retry task":
            task_id = self._select_task_id()
            if task_id:
                task = self.control_plane.task_service.retry_task(task_id)
                self.console.print(f"[green]Retried[/green] {task.task_id} -> {task.status.value}")
        elif choice == "Cancel task":
            task_id = self._select_task_id()
            if task_id:
                task = self.control_plane.task_service.cancel_task(task_id)
                self.console.print(f"[yellow]Cancelled[/yellow] {task.task_id} -> {task.status.value}")

    def _approvals_menu(self) -> None:
        choice = self._choose("Approvals", ["Pending inbox", "All approvals", "Create approval", "Back"])
        if choice == "Pending inbox":
            self.console.print(build_approvals_table(self.control_plane.list_approvals(pending_only=True)))
        elif choice == "All approvals":
            self.console.print(build_approvals_table(self.control_plane.list_approvals()))
        elif choice == "Create approval":
            project_id = self._select_project_id()
            if project_id is None:
                return
            data = ApprovalCreateInput(
                approval_id=Prompt.ask("Approval ID"),
                project_id=project_id,
                target_type=Prompt.ask("Target type", default="freeze"),
                target_id=Prompt.ask("Target ID"),
                approved_by=Prompt.ask("Approved by"),
                decision=self._choose("Decision", ["pending", "approved", "rejected"]),
                comment=Prompt.ask("Comment", default=""),
            )
            approval = self.control_plane.create_approval(data)
            self.console.print(f"[green]Recorded approval[/green] {approval.approval_id}")

    def _runs_menu(self) -> None:
        choice = self._choose("Runs", ["List runs", "Watch runs", "Back"])
        if choice == "List runs":
            self.console.print(build_runs_table(self.control_plane.list_runs()))
        elif choice == "Watch runs":
            self._watch_runs()

    def _registries_menu(self) -> None:
        choice = self._choose(
            "Registries",
            [
                "Artifacts",
                "Paper cards",
                "Gap maps",
                "Claims",
                "Freeze status",
                "Back",
            ],
        )
        if choice == "Artifacts":
            self.console.print(build_artifacts_table(self.control_plane.list_artifacts()))
        elif choice == "Paper cards":
            self.console.print(build_paper_cards_table(self.control_plane.list_paper_cards()))
        elif choice == "Gap maps":
            self.console.print(build_gap_maps_table(self.control_plane.list_gap_maps()))
        elif choice == "Claims":
            claims = self.control_plane.list_claims()
            for claim in claims:
                self.console.print(f"{claim.claim_id} | {claim.claim_type} | {claim.risk_level} | {claim.text}")
        elif choice == "Freeze status":
            self.console.print(f"Topic freeze: {self.control_plane.get_topic_freeze()}")
            self.console.print(f"Spec freeze: {self.control_plane.get_spec_freeze()}")
            self.console.print(f"Results freeze: {self.control_plane.get_results_freeze()}")

    def _create_task_flow(self) -> None:
        project_id = self._select_project_id()
        if project_id is None:
            return
        kind = self._choose("Task kind", TASK_KIND_OPTIONS)
        topic = Prompt.ask("Topic", default="")
        source_title = ""
        source_abstract = ""
        source_setting = ""
        if kind in {"paper_ingest", "repo_ingest", "read_source"}:
            source_title = Prompt.ask("Source title", default="")
            source_abstract = Prompt.ask("Source abstract", default="")
            source_setting = Prompt.ask("Source setting", default="")
        task = self.control_plane.create_task(
            TaskCreateInput(
                task_id=Prompt.ask("Task ID"),
                project_id=project_id,
                kind=kind,
                goal=Prompt.ask("Goal"),
                owner=Prompt.ask("Owner", default="operator"),
                input_payload=self.control_plane.build_task_input_payload(
                    kind=kind,
                    topic=topic,
                    source_title=source_title,
                    source_abstract=source_abstract,
                    source_setting=source_setting,
                ),
                assigned_agent=Prompt.ask("Assigned agent (optional)", default="") or None,
                dispatch_profile=self._select_dispatch_profile(),
            )
        )
        self.console.print(f"[green]Created task[/green] {task.task_id}")

    def _dispatch_task_flow(self) -> None:
        task_id = self._select_task_id()
        if task_id is None:
            return
        run_async = Confirm.ask("Enqueue async via Celery?", default=False)
        result = self.control_plane.dispatch_task(task_id, run_async=run_async)
        if run_async:
            self.console.print(f"[green]Enqueued[/green] {task_id} as job {result.id}")
            return
        self.console.print(
            f"[green]Dispatched[/green] {result.task.task_id} -> "
            f"{result.task.status.value} ({result.result.status})"
        )
        if result.result.routing is not None:
            self.console.print(
                f"Routing: {result.result.routing.provider_name} / {result.result.routing.model or '<default>'}"
            )

    def _watch_tasks(self) -> None:
        self.console.print("Watching tasks. Press Ctrl+C to stop.")
        try:
            with Live(build_tasks_table(self.control_plane.list_tasks()), console=self.console, refresh_per_second=1) as live:
                while True:
                    live.update(build_tasks_table(self.control_plane.list_tasks()))
                    time.sleep(self.refresh_interval)
        except KeyboardInterrupt:
            self.console.print("Stopped task watch.")

    def _watch_runs(self) -> None:
        self.console.print("Watching runs. Press Ctrl+C to stop.")
        try:
            with Live(build_runs_table(self.control_plane.list_runs()), console=self.console, refresh_per_second=1) as live:
                while True:
                    live.update(build_runs_table(self.control_plane.list_runs()))
                    time.sleep(self.refresh_interval)
        except KeyboardInterrupt:
            self.console.print("Stopped run watch.")

    def _select_project_id(self) -> str | None:
        projects = self.control_plane.list_projects()
        if not projects:
            self.console.print("[yellow]No projects available. Create a project first.[/yellow]")
            return None
        options = [f"{project.project_id} | {project.name}" for project in projects]
        selection = self._choose("Select project", options)
        return selection.split(" | ", 1)[0]

    def _select_task_id(self) -> str | None:
        tasks = self.control_plane.list_tasks()
        if not tasks:
            self.console.print("[yellow]No tasks available.[/yellow]")
            return None
        options = [f"{task.task_id} | {task.kind} | {task.status.value}" for task in tasks]
        selection = self._choose("Select task", options)
        return selection.split(" | ", 1)[0]

    def _select_dispatch_profile(self):
        choices = available_dispatch_profile_choices(self.control_plane.system_dispatch_profile())
        labels = [choice.label for choice in choices] + ["Custom provider/model"]
        selected = self._choose("Dispatch profile", labels)
        if selected == "Custom provider/model":
            provider_name = self._choose("Provider", self.control_plane.provider_names())
            known_models = [choice.model for choice in available_model_choices(provider_name)]
            if known_models:
                model = self._choose("Model", known_models + ["Custom"])
                if model == "Custom":
                    model = Prompt.ask("Model")
            else:
                model = Prompt.ask("Model")
            max_steps_raw = Prompt.ask("Max steps (optional)", default="")
            max_steps = int(max_steps_raw) if max_steps_raw.strip() else None
            profile_name = Prompt.ask("Profile name", default=f"{provider_name}-{model}")
            return build_dispatch_profile(provider_name, model, max_steps=max_steps, profile_name=profile_name)
        selected_choice = next(choice for choice in choices if choice.label == selected)
        return selected_choice.dispatch_profile

    def _choose(self, title: str, options: Sequence[str]) -> str:
        self.console.print(f"\n[bold]{title}[/bold]")
        for index, option in enumerate(options, start=1):
            self.console.print(f"{index}. {option}")
        selection = IntPrompt.ask("Select", choices=[str(index) for index in range(1, len(options) + 1)])
        return options[selection - 1]
