from pathlib import Path
import tomllib

import app.cli as cli_module
from app.cli import main
from app.db.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.db.sqlite import SQLiteDatabase


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


def test_cli_create_task_accepts_dispatch_profile(tmp_path: Path) -> None:
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
            "t-routing",
            "--project-id",
            "p1",
            "--kind",
            "paper_ingest",
            "--goal",
            "Ingest a paper",
            "--owner",
            "gabriel",
            "--dispatch-profile",
            '{"provider":{"provider_name":"codex","model":"gpt-5.4"},"max_steps":18}',
        ]
    ) == 0

    repository = SQLiteTaskRepository(SQLiteDatabase(db_path))
    task = repository.get_by_id("t-routing")

    assert task is not None
    assert task.dispatch_profile is not None
    assert task.dispatch_profile.provider is not None
    assert task.dispatch_profile.provider.provider_name == "codex"
    assert task.dispatch_profile.max_steps == 18


def test_cli_can_create_lessons_and_verify_runs(capsys, tmp_path: Path) -> None:
    db_path = tmp_path / "researchos.db"

    assert main(
        [
            "--db-path",
            str(db_path),
            "create-lesson",
            "--lesson-id",
            "lesson-1",
            "--lesson-kind",
            "failure_signature",
            "--title",
            "Missing ablation",
            "--summary",
            "Builder skipped the baseline ablation.",
            "--task-kind",
            "implement_experiment",
            "--agent-name",
            "builder_agent",
        ]
    ) == 0
    assert main(["--db-path", str(db_path), "list-lessons", "--task-kind", "implement_experiment"]) == 0

    assert main(
        [
            "--db-path",
            str(db_path),
            "create-run",
            "--run-id",
            "run-1",
            "--spec-id",
            "spec-1",
            "--git-commit",
            "abc123",
            "--config-hash",
            "cfg",
            "--dataset-snapshot",
            "dataset-v1",
            "--seed",
            "7",
            "--gpu",
            "A100",
        ]
    ) == 0
    assert main(["--db-path", str(db_path), "verify-run", "--run-id", "run-1"]) == 0
    output = capsys.readouterr().out

    assert "Created lesson lesson-1" in output
    assert "lesson-1\tfailure_signature\timplement_experiment\tbuilder_agent" in output
    assert "run:run-1\trun_manifest_sanity\tverified" in output


def test_cli_no_subcommand_launches_console(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "researchos.db"
    launched: dict[str, bool] = {"value": False}

    def fake_run(self) -> int:
        launched["value"] = True
        return 0

    monkeypatch.setattr(cli_module.TerminalControlPlaneApp, "run", fake_run)

    assert main(["--db-path", str(db_path)]) == 0
    assert launched["value"] is True


def test_cli_console_subcommand_launches_same_console(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "researchos.db"
    launched: dict[str, bool] = {"value": False}

    def fake_run(self) -> int:
        launched["value"] = True
        return 0

    monkeypatch.setattr(cli_module.TerminalControlPlaneApp, "run", fake_run)

    assert main(["--db-path", str(db_path), "console"]) == 0
    assert launched["value"] is True


def test_pyproject_registers_researchos_and_ros_entrypoints() -> None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]

    assert scripts["researchos"] == "app.cli:main"
    assert scripts["ros"] == "app.cli:main"
