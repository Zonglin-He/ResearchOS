from pathlib import Path

from app.cli import main


def test_cli_can_create_and_list_project(capsys, tmp_path: Path) -> None:
    db_path = tmp_path / "researchos.db"

    assert main(
        [
            "--db-path",
            str(db_path),
            "create-project",
            "--project-id",
            "p1",
            "--name",
            "ResearchOS",
            "--description",
            "CLI test project",
        ]
    ) == 0

    assert main(["--db-path", str(db_path), "list-projects"]) == 0
    output = capsys.readouterr().out

    assert "Created project p1" in output
    assert "p1\tResearchOS\tactive" in output


def test_cli_can_create_and_update_task(capsys, tmp_path: Path) -> None:
    db_path = tmp_path / "researchos.db"
    main(
        [
            "--db-path",
            str(db_path),
            "create-project",
            "--project-id",
            "p1",
            "--name",
            "ResearchOS",
            "--description",
            "CLI test project",
        ]
    )

    assert main(
        [
            "--db-path",
            str(db_path),
            "create-task",
            "--task-id",
            "t1",
            "--project-id",
            "p1",
            "--kind",
            "paper_ingest",
            "--goal",
            "Ingest a paper",
            "--owner",
            "gabriel",
        ]
    ) == 0

    assert main(
        [
            "--db-path",
            str(db_path),
            "update-task-status",
            "--task-id",
            "t1",
            "--status",
            "running",
        ]
    ) == 0

    assert main(["--db-path", str(db_path), "list-tasks", "--project-id", "p1"]) == 0
    output = capsys.readouterr().out

    assert "Created task t1" in output
    assert "Updated task t1 to running" in output
    assert "t1\tp1\tpaper_ingest\trunning" in output
