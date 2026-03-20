from __future__ import annotations

from app.db.models import ProjectModel
from app.schemas.project import Project


class SAProjectRepository:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def create(self, project: Project) -> Project:
        model = ProjectModel(
            project_id=project.project_id,
            name=project.name,
            description=project.description,
            status=project.status,
            created_at=project.created_at,
        )
        with self.session_factory() as session:
            session.merge(model)
            session.commit()
        return project

    def get_by_id(self, project_id: str) -> Project | None:
        with self.session_factory() as session:
            model = session.get(ProjectModel, project_id)
            if model is None:
                return None
            return Project(
                project_id=model.project_id,
                name=model.name,
                description=model.description,
                status=model.status,
                created_at=model.created_at,
            )

    def list_all(self) -> list[Project]:
        with self.session_factory() as session:
            models = session.query(ProjectModel).order_by(ProjectModel.created_at).all()
        return [
            Project(
                project_id=model.project_id,
                name=model.name,
                description=model.description,
                status=model.status,
                created_at=model.created_at,
            )
            for model in models
        ]

    def delete(self, project_id: str) -> None:
        with self.session_factory() as session:
            model = session.get(ProjectModel, project_id)
            if model is not None:
                session.delete(model)
                session.commit()
