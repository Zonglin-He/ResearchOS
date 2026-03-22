from __future__ import annotations

from datetime import datetime
import json

from app.core.enums import Stage
from app.db.repositories.project_repository import ProjectRepository
from app.db.sqlite import SQLiteDatabase
from app.routing import dispatch_profile_from_dict
from app.schemas.project import Project
from app.services.registry_store import to_record


class SQLiteProjectRepository(ProjectRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def create(self, project: Project) -> Project:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO projects (
                    project_id, name, description, status, stage, dispatch_profile_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.project_id,
                    project.name,
                    project.description,
                    project.status,
                    project.stage.value,
                    json.dumps(to_record(project.dispatch_profile))
                    if project.dispatch_profile is not None
                    else None,
                    project.created_at.isoformat(),
                ),
            )
        return project

    def get_by_id(self, project_id: str) -> Project | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_project(row)

    def list_all(self) -> list[Project]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY created_at, project_id"
            ).fetchall()
        return [self._row_to_project(row) for row in rows]

    def delete(self, project_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))

    @staticmethod
    def _row_to_project(row: object) -> Project:
        return Project(
            project_id=row["project_id"],
            name=row["name"],
            description=row["description"],
            status=row["status"],
            stage=Stage(row["stage"]) if row["stage"] else Stage.NEW_TOPIC,
            dispatch_profile=dispatch_profile_from_dict(
                json.loads(row["dispatch_profile_json"])
                if row["dispatch_profile_json"]
                else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
