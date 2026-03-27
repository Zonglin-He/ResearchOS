from __future__ import annotations

from app.core.enums import Stage
from app.db.repositories.project_repository import ProjectRepository
from app.routing.models import DispatchProfile
from app.schemas.project import Project
from app.workflows.research_flow import (
    FlowEvent,
    ResearchFlowSnapshot,
    rollback_stage_for,
    transition_flow,
)

_FLOW_METADATA_KEY = "flow_state"


class ProjectService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    def create_project(self, project: Project) -> Project:
        if project.dispatch_profile is None:
            project.dispatch_profile = DispatchProfile(metadata={})
        created = self.repository.create(project)
        existing_snapshot = self._flow_snapshot_from_project(created)
        if existing_snapshot is not None:
            return created
        snapshot = transition_flow(
            None,
            event=FlowEvent.CREATE,
            stage=created.stage,
            note="project created",
        )
        return self._save_flow_snapshot(created, snapshot)

    def get_project(self, project_id: str) -> Project | None:
        return self.repository.get_by_id(project_id)

    def list_projects(self) -> list[Project]:
        return self.repository.list_all()

    def save_project(self, project: Project) -> Project:
        return self.repository.create(project)

    def get_flow_snapshot(self, project_id: str) -> ResearchFlowSnapshot:
        project = self.get_project(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        snapshot = self._flow_snapshot_from_project(project)
        if snapshot is not None:
            return snapshot
        snapshot = transition_flow(
            None,
            event=FlowEvent.CREATE,
            stage=project.stage,
            note="flow snapshot initialized",
        )
        self._save_flow_snapshot(project, snapshot)
        return snapshot

    def save_flow_snapshot(self, project_id: str, snapshot: ResearchFlowSnapshot) -> Project:
        project = self.get_project(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        return self._save_flow_snapshot(project, snapshot)

    def transition_flow(
        self,
        project_id: str,
        *,
        event: FlowEvent,
        stage: Stage | None = None,
        task_id: str | None = None,
        note: str = "",
    ) -> Project:
        project = self.get_project(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        current = self._flow_snapshot_from_project(project)
        snapshot = transition_flow(
            current,
            event=event,
            stage=stage,
            task_id=task_id,
            note=note,
        )
        return self._save_flow_snapshot(project, snapshot)

    def update_stage(self, project_id: str, stage: Stage) -> Project:
        project = self.get_project(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        snapshot = self._flow_snapshot_from_project(project)
        if snapshot is None:
            synced = transition_flow(
                None,
                event=FlowEvent.CREATE,
                stage=stage,
                note="stage updated",
            )
        elif snapshot.stage == stage:
            project.stage = stage
            return self.repository.create(project)
        else:
            synced = transition_flow(
                snapshot,
                event=FlowEvent.SYNC_STAGE,
                stage=stage,
                note=f"stage synced to {stage.value}",
            )
        return self._save_flow_snapshot(project, synced)

    def delete_project(self, project_id: str) -> None:
        self.repository.delete(project_id)

    @staticmethod
    def _flow_snapshot_from_project(project: Project) -> ResearchFlowSnapshot | None:
        dispatch_profile = project.dispatch_profile
        if dispatch_profile is None:
            return None
        metadata = dispatch_profile.metadata if isinstance(dispatch_profile.metadata, dict) else {}
        payload = metadata.get(_FLOW_METADATA_KEY)
        if payload is None:
            return None
        return ResearchFlowSnapshot.from_metadata(payload, fallback_stage=project.stage)

    def _save_flow_snapshot(self, project: Project, snapshot: ResearchFlowSnapshot) -> Project:
        dispatch_profile = project.dispatch_profile
        if dispatch_profile is None:
            dispatch_profile = DispatchProfile(metadata={})
            project.dispatch_profile = dispatch_profile
        elif not isinstance(dispatch_profile.metadata, dict):
            dispatch_profile.metadata = {}
        dispatch_profile.metadata[_FLOW_METADATA_KEY] = snapshot.to_metadata()
        project.stage = snapshot.stage
        if snapshot.rollback_stage is None:
            dispatch_profile.metadata["rollback_stage"] = rollback_stage_for(snapshot.stage).value
        else:
            dispatch_profile.metadata["rollback_stage"] = snapshot.rollback_stage.value
        return self.repository.create(project)
