from app.db.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.db.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.db.sqlite import SQLiteDatabase
from app.schemas.project import Project
from app.schemas.task import Task


def main() -> None:
    database = SQLiteDatabase("data/researchos.db")
    database.initialize()
    project_repository = SQLiteProjectRepository(database)
    task_repository = SQLiteTaskRepository(database)

    project_repository.create(
        Project(
            project_id="demo",
            name="ResearchOS Demo",
            description="Seeded project",
            status="active",
        )
    )
    task_repository.create(
        Task(
            task_id="task_demo_001",
            project_id="demo",
            kind="paper_ingest",
            goal="Ingest a demo paper",
            input_payload={"paper_id": "demo"},
            owner="system",
        )
    )
    print("Seeded demo project and task.")


if __name__ == "__main__":
    main()
