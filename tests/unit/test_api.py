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


def test_api_can_create_imported_run_and_results_freeze_metadata(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    run_response = client.post(
        "/runs",
        json={
            "run_id": "run_imported",
            "spec_id": "spec_001",
            "git_commit": "external",
            "config_hash": "sha256:external",
            "dataset_snapshot": "dataset_v1",
            "seed": 11,
            "gpu": "external",
            "status": "completed",
            "metrics": {"accuracy": 0.88},
            "artifacts": ["artifact_table"],
            "source_type": "imported",
            "source_label": "baseline-paper",
            "source_metadata": {"repo": "https://github.com/example/baseline"},
            "notes": ["Imported from external experiment logs."],
        },
    )
    results_response = client.post(
        "/freezes/results",
        json={
            "results_id": "results_imported",
            "spec_id": "spec_001",
            "main_claims": ["claim_001"],
            "supporting_run_ids": ["run_imported"],
            "external_sources": ["table:paper-main"],
            "notes": ["Imported evidence package."],
        },
    )

    assert run_response.status_code == 200
    assert results_response.status_code == 200
    run = client.get("/runs").json()[0]
    results = client.get("/freezes/results").json()
    assert run["source_type"] == "imported"
    assert run["source_label"] == "baseline-paper"
    assert run["source_metadata"]["repo"] == "https://github.com/example/baseline"
    assert results["supporting_run_ids"] == ["run_imported"]
    assert results["external_sources"] == ["table:paper-main"]


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


def test_api_can_persist_spec_and_results_freezes(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    spec_response = client.post(
        "/freezes/spec",
        json={
            "spec_id": "spec_001",
            "topic_id": "topic_001",
            "hypothesis": ["robust optimization improves stability"],
            "must_beat_baselines": ["baseline_a"],
            "datasets": ["dataset_v1"],
            "metrics": ["accuracy"],
            "ablations": ["no_augmentation"],
            "approved_by": "gabriel",
        },
    )
    results_response = client.post(
        "/freezes/results",
        json={
            "results_id": "results_001",
            "spec_id": "spec_001",
            "main_claims": ["claim_001"],
            "tables": ["main_results"],
            "figures": ["curve_001"],
            "approved_by": "gabriel",
        },
    )

    assert spec_response.status_code == 200
    assert results_response.status_code == 200
    assert client.get("/freezes/spec").json()["spec_id"] == "spec_001"
    assert client.get("/freezes/results").json()["results_id"] == "results_001"


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
    assert detail["provenance"]["artifact_id"] == "artifact_001"
    assert detail["provenance"]["verification_links"][0]["verification_id"].startswith("verify:run:run_001")
    assert detail["annotations"] == []


def test_api_can_create_and_list_artifact_annotations(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db"), workspace_root=str(tmp_path)))
    artifact_path = tmp_path / "artifacts" / "note.txt"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("note", encoding="utf-8")

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
    client.app.state.artifact_service.register_artifact(
        ArtifactRecord(
            artifact_id="artifact_annotated",
            run_id="run_001",
            kind="note",
            path="artifacts/note.txt",
            hash="sha256:note",
        )
    )

    create_response = client.post(
        "/artifacts/artifact_annotated/annotations",
        json={
            "annotation_id": "ann_001",
            "operator": "gabriel",
            "status": "reviewed",
            "review_tags": ["important", "operator-note"],
            "note": "Reviewed during operator inspection.",
        },
    )
    list_response = client.get("/artifacts/artifact_annotated/annotations")
    detail_response = client.get("/artifacts/artifact_annotated")

    assert create_response.status_code == 200
    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert create_response.json()["status"] == "reviewed"
    assert list_response.json()[0]["annotation_id"] == "ann_001"
    assert detail_response.json()["annotations"][0]["review_tags"] == ["important", "operator-note"]


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


def test_api_exposes_project_dashboard_and_routing_surfaces(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db"), workspace_root=str(tmp_path)))

    client.post(
        "/projects",
        json={
            "project_id": "p1",
            "name": "Dashboard Project",
            "description": "dashboard test",
            "status": "active",
            "dispatch_profile": {
                "provider": {"provider_name": "local", "model": "deterministic-reader"},
                "max_steps": 12,
            },
        },
    )
    client.post(
        "/tasks",
        json={
            "task_id": "t1",
            "project_id": "p1",
            "kind": "paper_ingest",
            "goal": "Read one source",
            "input_payload": {
                "topic": "retrieval",
                "source_summary": {
                    "title": "Dashboard Source",
                    "abstract": "Compact summary.",
                    "setting": "streaming retrieval",
                },
            },
            "owner": "tester",
            "dispatch_profile": {
                "provider": {"provider_name": "local", "model": "deterministic-reader"},
            },
        },
    )
    client.post("/tasks/t1/dispatch")

    dashboard = client.get("/projects/p1/dashboard")
    system_routing = client.get("/routing/system")
    task_routing = client.get("/routing/tasks/t1")
    provider_health = client.get("/providers/health")

    assert dashboard.status_code == 200
    assert dashboard.json()["project_id"] == "p1"
    assert dashboard.json()["artifact_count"] >= 1
    assert dashboard.json()["storage_boundary"]["registry_dir"].endswith("registry")
    assert system_routing.status_code == 200
    assert "resolved_dispatch" in system_routing.json()
    assert task_routing.status_code == 200
    assert task_routing.json()["resolved_dispatch"]["provider_name"] == "local"
    assert provider_health.status_code == 200
    assert any(item["provider_family"] == "local" for item in provider_health.json())


def test_api_can_disable_and_enable_provider_family(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db"), workspace_root=str(tmp_path)))

    disable_response = client.post("/providers/gemini/disable")
    enable_response = client.post("/providers/gemini/enable")

    assert disable_response.status_code == 200
    assert disable_response.json()["provider_family"] == "gemini"
    assert disable_response.json()["state"] == "disabled"
    assert enable_response.status_code == 200
    assert enable_response.json()["provider_family"] == "gemini"


def test_api_can_return_artifact_inspection_surface(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db"), workspace_root=str(tmp_path)))
    artifact_path = tmp_path / "artifacts" / "inspect.txt"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("artifact", encoding="utf-8")

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
    client.app.state.artifact_service.register_artifact(
        ArtifactRecord(
            artifact_id="artifact_inspect",
            run_id="run_001",
            kind="note",
            path="artifacts/inspect.txt",
            hash="sha256:inspect",
        )
    )

    response = client.get("/artifacts/artifact_inspect/inspect")

    assert response.status_code == 200
    assert response.json()["artifact_id"] == "artifact_inspect"
    assert response.json()["exists_on_disk"] is True
