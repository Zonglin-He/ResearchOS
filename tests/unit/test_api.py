from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import create_app


def test_api_can_create_project_and_task(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    project_response = client.post(
        "/projects",
        json={
            "project_id": "p1",
            "name": "ResearchOS",
            "description": "API test project",
            "status": "active",
        },
    )
    task_response = client.post(
        "/tasks",
        json={
            "task_id": "t1",
            "project_id": "p1",
            "kind": "paper_ingest",
            "goal": "Ingest a paper",
            "input_payload": {},
            "owner": "gabriel",
        },
    )

    assert project_response.status_code == 200
    assert task_response.status_code == 200
    assert task_response.json()["project_id"] == "p1"


def test_api_updates_task_status(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))
    client.post(
        "/projects",
        json={
            "project_id": "p1",
            "name": "ResearchOS",
            "description": "API test project",
            "status": "active",
        },
    )
    client.post(
        "/tasks",
        json={
            "task_id": "t1",
            "project_id": "p1",
            "kind": "paper_ingest",
            "goal": "Ingest a paper",
            "input_payload": {},
            "owner": "gabriel",
        },
    )

    response = client.post("/tasks/t1/status", json={"status": "running"})

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_api_can_create_claim_and_run(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    claim_response = client.post(
        "/claims",
        json={
            "claim_id": "claim_001",
            "text": "Model improves robustness",
            "claim_type": "performance",
        },
    )
    run_response = client.post(
        "/runs",
        json={
            "run_id": "run_001",
            "spec_id": "spec_001",
            "git_commit": "abc123",
            "config_hash": "sha256:123",
            "dataset_snapshot": "dataset_v1",
            "seed": 42,
            "gpu": "A100",
        },
    )

    assert claim_response.status_code == 200
    assert run_response.status_code == 200
    assert claim_response.json()["claim_id"] == "claim_001"
    assert run_response.json()["run_id"] == "run_001"


def test_api_can_create_and_list_pending_approvals(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    create_response = client.post(
        "/approvals",
        json={
            "approval_id": "approval_001",
            "project_id": "p1",
            "target_type": "freeze",
            "target_id": "spec_001",
            "approved_by": "gabriel",
            "decision": "pending",
            "comment": "",
        },
    )
    list_response = client.get("/approvals/pending")

    assert create_response.status_code == 200
    assert list_response.status_code == 200
    assert list_response.json()[0]["approval_id"] == "approval_001"


def test_api_can_persist_paper_gap_and_freeze_assets(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    paper_response = client.post(
        "/paper-cards",
        json={
            "paper_id": "paper_001",
            "title": "A Paper",
            "problem": "Robustness",
            "setting": "Streaming shift",
            "task_type": "classification",
            "evidence_refs": [{"section": "method", "page": 4}],
        },
    )
    gap_response = client.post(
        "/gap-maps",
        json={
            "topic": "streaming adaptation",
            "clusters": [
                {
                    "name": "assumption fragility",
                    "gaps": [{"gap_id": "gap_001", "description": "Stable stats assumption"}],
                }
            ],
        },
    )
    freeze_response = client.post(
        "/freezes/topic",
        json={
            "topic_id": "topic_001",
            "selected_gap_ids": ["gap_001"],
            "research_question": "Can purification improve robustness?",
            "novelty_type": ["setting"],
            "owner": "gabriel",
        },
    )

    assert paper_response.status_code == 200
    assert gap_response.status_code == 200
    assert freeze_response.status_code == 200
    assert client.get("/paper-cards").json()[0]["paper_id"] == "paper_001"
    assert client.get("/gap-maps").json()[0]["topic"] == "streaming adaptation"
    assert client.get("/freezes/topic").json()["topic_id"] == "topic_001"
