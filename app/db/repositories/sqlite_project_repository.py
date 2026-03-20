from __future__ import annotations

from datetime import datetime

from app.db.repositories.project_repository import ProjectRepository
from app.db.sqlite import SQLiteDatabase
from app.schemas.project import Project


class SQLiteProjectRepository(ProjectRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def create(self, project: Project) -> Project:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO projects (
                    project_id, name, description, status, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project.project_id,
                    project.name,
                    project.description,
                    project.status,
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
            created_at=datetime.fromisoformat(row["created_at"]),
        )
