from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.schemas.artifact import ArtifactRecord


def test_api_can_create_project_and_task(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    project_response = client.post(
        "/projects",
        json={
            "project_id": "p1",
            "name": "ResearchOS",
            "description": "API test project",
            "status": "active",
            "dispatch_profile": {
                "provider": {
                    "provider_name": "claude",
                    "model": "sonnet",
                }
            },
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
            "dispatch_profile": {
                "provider": {
                    "provider_name": "codex",
                    "model": "gpt-5.4",
                }
            },
        },
    )

    assert project_response.status_code == 200
    assert task_response.status_code == 200
    assert task_response.json()["project_id"] == "p1"
    assert project_response.json()["dispatch_profile"]["provider"]["provider_name"] == "claude"
    assert task_response.json()["dispatch_profile"]["provider"]["provider_name"] == "codex"


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


def test_api_rejects_invalid_paper_card_payload(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    response = client.post(
        "/paper-cards",
        json={
            "paper_id": "paper_001",
            "problem": "Robustness",
            "setting": "Streaming shift",
            "task_type": "classification",
        },
    )

    assert response.status_code == 422
    assert "title" in response.text


def test_api_rejects_invalid_gap_map_payload(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    response = client.post(
        "/gap-maps",
        json={
            "topic": "streaming adaptation",
            "clusters": [
                {
                    "name": "assumption fragility",
                    "gaps": [{"description": "Stable stats assumption"}],
                }
            ],
        },
    )

    assert response.status_code == 422
    assert "gap_id" in response.text


def test_api_rejects_invalid_topic_freeze_payload(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    response = client.post(
        "/freezes/topic",
        json={
            "topic_id": "topic_001",
            "selected_gap_ids": "gap_001",
            "research_question": "Can purification improve robustness?",
        },
    )

    assert response.status_code == 422
    assert "selected_gap_ids" in response.text


def test_api_rejects_invalid_spec_freeze_payload(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    response = client.post(
        "/freezes/spec",
        json={
            "spec_id": "spec_001",
            "topic_id": "topic_001",
            "hypothesis": "should be a list",
        },
    )

    assert response.status_code == 422
    assert "hypothesis" in response.text


def test_api_rejects_invalid_results_freeze_payload(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    response = client.post(
        "/freezes/results",
        json={
            "results_id": "results_001",
            "spec_id": "spec_001",
            "main_claims": "claim-1",
        },
    )

    assert response.status_code == 422
    assert "main_claims" in response.text


def test_api_can_create_and_filter_lessons(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    create_response = client.post(
        "/lessons",
        json={
            "lesson_id": "lesson_001",
            "lesson_kind": "failure_signature",
            "title": "Missing baseline ablation",
            "summary": "Builder skipped the baseline ablation.",
            "task_kind": "implement_experiment",
            "agent_name": "builder_agent",
            "provider_name": "codex",
            "model_name": "gpt-5.4",
            "failure_type": "ablation_gap",
        },
    )
    list_response = client.get("/lessons", params={"task_kind": "implement_experiment"})

    assert create_response.status_code == 200
    assert list_response.status_code == 200
    assert list_response.json()[0]["lesson_id"] == "lesson_001"


def test_api_can_verify_run_and_expose_audit_report(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))
    client.post(
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

    verification_response = client.post("/verifications/runs/run_001")
    audit_response = client.get("/audit/runs/run_001")

    assert verification_response.status_code == 200
    assert verification_response.json()["status"] == "verified"
    assert audit_response.status_code == 200
    assert audit_response.json()["report_type"] == "run_verification_report"


def test_api_rejects_invalid_lesson_kind(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    response = client.post(
        "/lessons",
        json={
            "lesson_id": "lesson_001",
            "lesson_kind": "unknown",
            "title": "Bad lesson",
            "summary": "Should fail validation.",
        },
    )

    assert response.status_code == 422
    assert "lesson_kind" in response.text


def test_api_can_return_artifact_detail_with_verification_links(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db"), workspace_root=str(tmp_path)))
    artifact_path = tmp_path / "artifacts" / "table.csv"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("metric,value\nacc,0.91\n", encoding="utf-8")

    client.post(
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
    run = client.app.state.run_service.get_run("run_001")
    assert run is not None
    run.artifacts = ["artifact_001"]
    client.app.state.run_service.update_run(run)
    client.app.state.artifact_service.register_artifact(
        ArtifactRecord(
            artifact_id="artifact_001",
            run_id="run_001",
            kind="table",
            path="artifacts/table.csv",
            hash="sha256:table",
            metadata={"table_name": "main_results"},
        )
    )
    verification_response = client.post("/verifications/runs/run_001")
    assert verification_response.status_code == 200

    detail_response = client.get("/artifacts/artifact_001")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["artifact_id"] == "artifact_001"
    assert detail["exists_on_disk"] is True
    assert detail["workspace_relative_path"] == "artifacts\\table.csv" or detail["workspace_relative_path"] == "artifacts/table.csv"
    assert detail["related_verifications"][0]["subject_id"] == "run_001"
    assert "run:run_001" in detail["evidence_refs"]


def test_api_can_return_audit_and_verification_summaries(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db"), workspace_root=str(tmp_path)))
    artifact_path = tmp_path / "artifacts" / "summary.txt"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("hello", encoding="utf-8")

    client.post(
        "/claims",
        json={
            "claim_id": "claim_001",
            "text": "Model improves robustness",
            "claim_type": "performance",
        },
    )
    client.post(
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
    run = client.app.state.run_service.get_run("run_001")
    assert run is not None
    run.artifacts = ["artifact_001"]
    client.app.state.run_service.update_run(run)
    client.app.state.artifact_service.register_artifact(
        ArtifactRecord(
            artifact_id="artifact_001",
            run_id="run_001",
            kind="note",
            path="artifacts/summary.txt",
            hash="sha256:note",
        )
    )
    client.post("/verifications/runs/run_001")

    audit_summary = client.get("/audit/summary")
    verification_summary = client.get("/verifications/summary")

    assert audit_summary.status_code == 200
    assert verification_summary.status_code == 200
    assert audit_summary.json()["total_reports"] >= 2
    assert audit_summary.json()["entry_status_counts"]["warn"] >= 1
    assert verification_summary.json()["total_checks"] >= 1
    assert verification_summary.json()["status_counts"]["verified"] >= 1
