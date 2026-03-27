from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import create_app


def test_discussion_flow_supports_import_adopt_and_promotions(tmp_path: Path) -> None:
    client = TestClient(create_app(str(tmp_path / "researchos.db"), workspace_root=str(tmp_path)))

    client.post(
        "/projects",
        json={
            "project_id": "p-discuss",
            "name": "Discussion Project",
            "description": "Study run anomalies and claim quality.",
            "status": "active",
        },
    )
    client.post(
        "/paper-cards",
        json={
            "paper_id": "10.1000/test-doi",
            "title": "Test Paper",
            "problem": "Robustness drift",
            "setting": "Streaming",
            "task_type": "classification",
        },
    )
    client.post(
        "/claims",
        json={
            "claim_id": "claim-discuss-1",
            "text": "Claim needs verification",
            "claim_type": "result",
        },
    )

    create_response = client.post(
        "/discussions",
        json={
            "session_id": "discussion-1",
            "project_id": "p-discuss",
            "title": "Run audit debate",
            "source_type": "web_handoff",
            "branch_kind": "negative-results-branch",
            "target_kind": "project",
            "target_id": "p-discuss",
            "target_label": "Discussion Project",
            "focus_question": "What should we do before trusting the result?",
            "attached_entities": [
                {"entity_type": "paper_card", "entity_id": "10.1000/test-doi", "label": "Test Paper"},
                {"entity_type": "claim", "entity_id": "claim-discuss-1", "label": "Claim needs verification"},
            ],
        },
    )

    assert create_response.status_code == 200
    assert create_response.json()["context_bundle"]["handoff_packet"]

    import_response = client.post(
        "/discussions/discussion-1/import",
        json={
            "source_mode": "web",
            "provider_label": "gpt-5-web",
            "transcript_title": "Web debate",
            "verbatim_text": (
                "Finding: the current claim is under-supported.\n"
                "Risk: metrics may be cherry-picked.\n"
                "Next: verify claim-discuss-1 and revisit DOI 10.1000/test-doi.\n"
                "Open question: should we freeze results before another audit?"
            ),
        },
    )

    assert import_response.status_code == 200
    imported = import_response.json()
    assert imported["status"] == "imported"
    assert imported["machine_distilled"]["summary"]
    assert imported["coverage_report"]["checks"]

    adopt_response = client.post(
        "/discussions/discussion-1/adopt",
        json={"approved_by": "operator", "route_to_kb": True},
    )
    assert adopt_response.status_code == 200
    adopted = adopt_response.json()
    assert adopted["status"] == "adopted"
    assert adopted["promoted_record_ids"]["kb"]

    approval_response = client.post(
        "/discussions/discussion-1/promote/approval",
        json={"approved_by": "operator"},
    )
    task_response = client.post(
        "/discussions/discussion-1/promote/task",
        json={"owner": "operator"},
    )

    assert approval_response.status_code == 200
    assert task_response.status_code == 200
    assert approval_response.json()["promotion_type"] == "approval"
    assert task_response.json()["promotion_type"] == "task"

    discussion_list = client.get("/discussions", params={"project_id": "p-discuss"})
    assert discussion_list.status_code == 200
    assert len(discussion_list.json()) == 1

    kb_questions = client.get("/kb/open_questions")
    assert kb_questions.status_code == 200
    assert kb_questions.json()
