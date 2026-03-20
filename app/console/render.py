from __future__ import annotations

from rich.table import Table


def build_projects_table(projects) -> Table:
    table = Table(title="Projects")
    table.add_column("Project ID")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Routing")
    for project in projects:
        provider = "-"
        model = "-"
        if project.dispatch_profile is not None and project.dispatch_profile.provider is not None:
            provider = project.dispatch_profile.provider.provider_name
            model = project.dispatch_profile.provider.model or "-"
        table.add_row(project.project_id, project.name, project.status, f"{provider} / {model}")
    return table


def build_tasks_table(tasks) -> Table:
    table = Table(title="Tasks")
    table.add_column("Task ID")
    table.add_column("Project")
    table.add_column("Kind")
    table.add_column("Status")
    table.add_column("Provider")
    table.add_column("Model")
    for task in tasks:
        provider = "-"
        model = "-"
        if task.last_run_routing is not None:
            provider = task.last_run_routing.provider_name
            model = task.last_run_routing.model or "-"
        elif task.dispatch_profile is not None and task.dispatch_profile.provider is not None:
            provider = task.dispatch_profile.provider.provider_name
            model = task.dispatch_profile.provider.model or "-"
        table.add_row(task.task_id, task.project_id, task.kind, task.status.value, provider, model)
    return table


def build_approvals_table(approvals) -> Table:
    table = Table(title="Approvals")
    table.add_column("Approval ID")
    table.add_column("Project")
    table.add_column("Target")
    table.add_column("Decision")
    table.add_column("By")
    for approval in approvals:
        table.add_row(
            approval.approval_id,
            approval.project_id,
            f"{approval.target_type}:{approval.target_id}",
            approval.decision,
            approval.approved_by,
        )
    return table


def build_runs_table(runs) -> Table:
    table = Table(title="Runs")
    table.add_column("Run ID")
    table.add_column("Spec")
    table.add_column("Status")
    table.add_column("Provider")
    table.add_column("Model")
    for run in runs:
        provider = run.dispatch_routing.provider_name if run.dispatch_routing is not None else "-"
        model = run.dispatch_routing.model if run.dispatch_routing is not None else "-"
        table.add_row(run.run_id, run.spec_id, run.status, provider, model or "-")
    return table


def build_artifacts_table(artifacts) -> Table:
    table = Table(title="Artifacts")
    table.add_column("Artifact ID")
    table.add_column("Run ID")
    table.add_column("Kind")
    table.add_column("Path")
    for artifact in artifacts:
        table.add_row(artifact.artifact_id, artifact.run_id, artifact.kind, artifact.path)
    return table


def build_paper_cards_table(cards) -> Table:
    table = Table(title="Paper Cards")
    table.add_column("Paper ID")
    table.add_column("Title")
    table.add_column("Task Type")
    for card in cards:
        table.add_row(card.paper_id, card.title, card.task_type)
    return table


def build_gap_maps_table(gap_maps) -> Table:
    table = Table(title="Gap Maps")
    table.add_column("Topic")
    table.add_column("Clusters")
    for gap_map in gap_maps:
        table.add_row(gap_map.topic, str(len(gap_map.clusters)))
    return table
