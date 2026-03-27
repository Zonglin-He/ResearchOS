from fastapi.testclient import TestClient

from app.api.app import create_app


def test_dispatch_workflow_via_api_resolves_profile_and_persists_registry_outputs(
    tmp_path,
) -> None:
    client = TestClient(
        create_app(
            str(tmp_path / "researchos.db"),
            workspace_root=str(tmp_path),
        )
    )

    project_response = client.post(
        "/projects",
        json={
            "project_id": "p1",
            "name": "Integration Project",
            "description": "dispatch workflow integration test",
            "status": "active",
            "dispatch_profile": {
                "provider": {"provider_name": "local", "model": "deterministic-reader"},
                "max_steps": 12,
            },
        },
    )
    assert project_response.status_code == 200

    task_response = client.post(
        "/tasks",
        json={
            "task_id": "t1",
            "project_id": "p1",
            "kind": "paper_ingest",
            "goal": "Ingest one source summary",
            "input_payload": {
                "topic": "retrieval",
                "source_summary": {
                    "title": "Integration Paper",
                    "abstract": "A compact summary for dispatch integration.",
                    "setting": "streaming retrieval",
                },
            },
            "owner": "integration",
            "dispatch_profile": {
                "provider": {"provider_name": "local", "model": "deterministic-reader"},
                "max_steps": 18,
            },
        },
    )
    assert task_response.status_code == 200

    dispatch_response = client.post("/tasks/t1/dispatch")
    assert dispatch_response.status_code == 200
    assert dispatch_response.json()["status"] == "succeeded"
    assert dispatch_response.json()["last_run_routing"]["provider_name"] == "local"
    assert dispatch_response.json()["last_run_routing"]["model"] == "deterministic-reader"

    task_read = client.get("/tasks/t1")
    paper_cards = client.get("/paper-cards")
    artifacts = client.get("/artifacts")

    assert task_read.status_code == 200
    assert task_read.json()["last_run_routing"]["provider_name"] == "local"
    assert paper_cards.status_code == 200
    assert paper_cards.json()[0]["paper_id"] == "integration_paper"
    assert artifacts.status_code == 200
    assert artifacts.json()[0]["kind"] == "reader_note"
    assert artifacts.json()[0]["run_id"] == "run-t1"
