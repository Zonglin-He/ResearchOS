from __future__ import annotations

from rich.panel import Panel
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


def build_project_dashboard_panel(dashboard) -> Panel:
    lines = [
        f"Project: {dashboard.project_name} ({dashboard.project_id})",
        f"Status: {dashboard.project_status}",
        "",
        "Task counts:",
        f"- total={dashboard.total_tasks} queued={dashboard.queued_tasks} running={dashboard.running_tasks} "
        f"waiting_approval={dashboard.waiting_approval_tasks} succeeded={dashboard.succeeded_tasks} "
        f"failed={dashboard.failed_tasks} cancelled={dashboard.cancelled_tasks}",
        "",
        "Artifacts and registries:",
        f"- artifacts={dashboard.artifact_count} paper_cards={dashboard.paper_card_count} "
        f"gap_maps={dashboard.gap_map_count} runs={dashboard.run_count}",
        "",
        "Freeze state:",
        f"- topic={dashboard.topic_freeze_present} spec={dashboard.spec_freeze_present} results={dashboard.results_freeze_present}",
    ]
    if dashboard.latest_task_ids:
        lines.extend(["", f"Latest tasks: {', '.join(dashboard.latest_task_ids)}"])
    if dashboard.recommended_next_task_kind is not None:
        lines.extend(
            [
                "",
                f"Recommended next task: {dashboard.recommended_next_task_kind}",
                f"Why: {dashboard.recommendation_reason}",
                f"Expected artifact: {dashboard.expected_artifact}",
            ]
        )
        if dashboard.likely_next_task_kind is not None:
            lines.append(f"Likely follow-up: {dashboard.likely_next_task_kind}")
    if dashboard.storage_boundary is not None:
        lines.extend(
            [
                "",
                "Storage boundary:",
                f"- database={dashboard.storage_boundary.database_backend} @ {dashboard.storage_boundary.database_location}",
                f"- registry={dashboard.storage_boundary.registry_dir}",
                f"- artifacts={dashboard.storage_boundary.artifacts_dir}",
                f"- state={dashboard.storage_boundary.state_dir}",
            ]
        )
    return Panel.fit("\n".join(lines), title="Project Dashboard")


def build_provider_health_table(snapshots) -> Table:
    table = Table(title="Provider Health")
    table.add_column("Provider")
    table.add_column("State")
    table.add_column("CLI")
    table.add_column("Disabled")
    table.add_column("Cooldown")
    table.add_column("Failure")
    for snapshot in snapshots:
        table.add_row(
            snapshot.provider_family,
            snapshot.state,
            "yes" if snapshot.cli_installed else "no",
            "yes" if snapshot.manually_disabled else "no",
            str(snapshot.cooldown_seconds_remaining),
            snapshot.failure_class or "-",
        )
    return table


def build_routing_inspection_panel(inspection) -> Panel:
    dispatch = inspection.resolved_dispatch
    lines = [
        f"Scope: {inspection.scope}",
        f"Subject: {inspection.subject_id or '-'}",
        f"Provider: {dispatch.provider_name}",
        f"Model: {dispatch.model or '<default>'}",
        f"Role: {dispatch.role_name or '-'}",
        f"Capability: {dispatch.capability_class or '-'}",
        f"Decision reason: {dispatch.decision_reason or '-'}",
        f"Fallback reason: {dispatch.fallback_reason or '-'}",
        f"Fallback chain: {', '.join(dispatch.fallback_chain) if dispatch.fallback_chain else '-'}",
    ]
    if dispatch.sources:
        lines.append(f"Sources: {dispatch.sources}")
    if inspection.storage_boundary is not None:
        lines.extend(
            [
                "",
                f"Storage database: {inspection.storage_boundary.database_backend} @ {inspection.storage_boundary.database_location}",
                f"Storage registry: {inspection.storage_boundary.registry_dir}",
            ]
        )
    return Panel.fit("\n".join(lines), title="Routing Inspector")


def build_artifact_inspection_panel(inspection) -> Panel:
    lines = [
        f"Artifact: {inspection.artifact_id}",
        f"Run: {inspection.run_id}",
        f"Kind: {inspection.kind}",
        f"Path: {inspection.path}",
        f"Resolved path: {inspection.resolved_path}",
        f"Workspace-relative path: {inspection.workspace_relative_path or '-'}",
        f"Exists on disk: {inspection.exists_on_disk}",
        "",
        f"Verification links: {inspection.verification_count}",
        f"Audit entries: {inspection.audit_entry_count}",
        f"Annotations: {inspection.annotation_count}",
    ]
    if inspection.evidence_refs:
        lines.extend(["", f"Evidence refs: {', '.join(inspection.evidence_refs)}"])
    if inspection.claim_supports:
        lines.append(f"Claim supports: {', '.join(inspection.claim_supports)}")
    if inspection.related_freeze_ids:
        lines.append(f"Related freezes: {', '.join(inspection.related_freeze_ids)}")
    return Panel.fit("\n".join(lines), title="Artifact Inspector")
