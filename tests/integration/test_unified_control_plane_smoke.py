from fastapi.testclient import TestClient

from app.api.app import create_app
from app.bootstrap import build_runtime_services
from app.cli import main
from app.console.control_plane import ConsoleControlPlane
from app.core.config import load_config


def test_unified_cli_api_console_smoke_flow(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "researchos.db"
    monkeypatch.setenv("RESEARCHOS_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("RESEARCHOS_PROVIDER", "local")
    monkeypatch.setenv("RESEARCHOS_PROVIDER_MODEL", "deterministic-reader")

    assert main(
        [
            "--db-path",
            str(db_path),
            "create-project",
            "--project-id",
            "p1",
            "--name",
            "Unified Flow",
            "--description",
            "unified control plane smoke",
        ]
    ) == 0

    client = TestClient(create_app(str(db_path), workspace_root=str(tmp_path)))
    task_response = client.post(
        "/tasks",
        json={
            "task_id": "t1",
            "project_id": "p1",
            "kind": "paper_ingest",
            "goal": "Read one source",
            "input_payload": {
                "topic": "retrieval",
                "source_summary": {
                    "title": "Unified Source",
                    "abstract": "Compact summary.",
                    "setting": "streaming retrieval",
                },
            },
            "owner": "tester",
            "dispatch_profile": {
                "provider": {"provider_name": "local", "model": "deterministic-reader"},
                "max_steps": 12,
            },
        },
    )
    assert task_response.status_code == 200

    dispatch_response = client.post("/tasks/t1/dispatch")
    assert dispatch_response.status_code == 200
    assert dispatch_response.json()["status"] == "succeeded"

    config = load_config()
    config.db_path = str(db_path)
    config.workspace_root = str(tmp_path)
    services = build_runtime_services(config)
    control_plane = ConsoleControlPlane.from_runtime_services(services)

    dashboard = control_plane.project_dashboard("p1")
    routing = control_plane.inspect_task_routing("t1")
    artifact_id = control_plane.list_artifacts()[0].artifact_id
    artifact = control_plane.inspect_artifact(artifact_id)

    assert dashboard.project_id == "p1"
    assert dashboard.artifact_count >= 1
    assert routing.resolved_dispatch.provider_name == "local"
    assert artifact.artifact_id == artifact_id
