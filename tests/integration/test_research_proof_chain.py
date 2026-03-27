from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.providers.local_provider import LocalProvider


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_guide_flow_experiment_writer_operator_proof_chain(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RESEARCHOS_PROVIDER", "local")
    monkeypatch.setenv("RESEARCHOS_PROVIDER_MODEL", "deterministic-reader")
    client = TestClient(create_app(str(tmp_path / "researchos.db"), workspace_root=str(tmp_path)))
    original_generate = LocalProvider.generate

    async def patched_generate(
        self,
        system_prompt: str,
        user_input: str,
        tools=None,
        response_schema=None,
        model=None,
        provider_config=None,
    ):
        try:
            payload = json.loads(user_input)
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict) and isinstance(payload.get("draft_output"), dict):
            reflected = dict(payload["draft_output"])
            audit_notes = list(reflected.get("audit_notes", []))
            audit_notes.append("integration proof chain preserved reflected draft output")
            reflected["audit_notes"] = audit_notes
            return reflected
        task_payload = payload.get("task", {}) if isinstance(payload, dict) else {}
        input_payload = task_payload.get("input_payload", {}) if isinstance(task_payload, dict) else {}
        task_kind = str(task_payload.get("kind", "")).strip()

        if task_kind == "hypothesis_draft":
            return {
                "summary": "Draft three falsifiable hypotheses from the selected gap.",
                "branches": _branch_specs(),
                "audit_notes": ["integration proof chain produced deterministic hypotheses"],
            }
        if task_kind == "branch_plan":
            return {
                "summary": "Expand the hypotheses into three executable branches.",
                "branches": _branch_specs(),
                "audit_notes": ["integration proof chain produced deterministic branch plans"],
            }
        if task_kind in {"implement_experiment", "reproduce_baseline", "build_spec"}:
            branch_id = str(input_payload.get("branch_id", "branch-main")).strip() or "branch-main"
            accuracy = {
                "branch-baseline": 0.84,
                "branch-main": 0.91,
                "branch-ablation": 0.79,
            }.get(branch_id, 0.88)
            loss = round(1.0 - accuracy, 2)
            script = (
                "import json\n"
                f"print('METRICS: ' + json.dumps({{'accuracy': {accuracy}, 'loss': {loss}}}))\n"
            )
            return {
                "summary": f"Execute deterministic experiment for {branch_id}.",
                "experiment_script": script,
                "execution_command": "python experiment.py",
                "artifacts": [
                    {
                        "artifact_id": f"{task_payload.get('task_id', branch_id)}-table",
                        "kind": "table",
                        "path": f"artifacts/{task_payload.get('task_id', branch_id)}/main_results.csv",
                        "hash": f"hash-{branch_id}",
                        "metadata": {"accuracy": accuracy, "loss": loss},
                    }
                ],
                "run_manifest": {
                    "run_id": f"run-{task_payload.get('task_id', branch_id)}",
                    "spec_id": str(input_payload.get("spec_id", "spec-proof")),
                    "git_commit": "proof-chain-commit",
                    "config_hash": f"cfg-{branch_id}",
                    "dataset_snapshot": "proof-dataset",
                    "seed": 0,
                    "gpu": "cpu",
                    "status": "completed",
                    "metrics": {"accuracy": accuracy, "loss": loss},
                    "artifacts": [f"{task_payload.get('task_id', branch_id)}-table"],
                    "experiment_branch": branch_id,
                },
                "claims": [
                    {
                        "claim_id": f"claim-{branch_id}",
                        "text": f"{branch_id} reaches {accuracy:.2f} accuracy.",
                        "claim_type": "result",
                        "supported_by_tables": [f"{task_payload.get('task_id', branch_id)}-table"],
                        "risk_level": "low",
                    }
                ],
                "audit_notes": [f"integration proof chain executed {branch_id}"],
            }
        if task_kind == "analyze_run":
            metrics = input_payload.get("metrics", {})
            branch_id = str(input_payload.get("branch_id", "branch-main")).strip() or "branch-main"
            return {
                "summary": f"{branch_id} is stable enough to draft.",
                "metrics": metrics,
                "execution_success": True,
                "anomalies": [],
                "recommended_actions": ["promote to writing"],
                "decision": "PROCEED",
                "decision_confidence": 0.95,
                "audit_notes": [f"integration proof chain promoted {branch_id}"],
            }
        if task_kind == "branch_review":
            return {
                "summary": "branch-main is the strongest branch after comparison.",
                "selected_branch_id": "branch-main",
                "winning_rationale": "branch-main achieved the best accuracy while preserving a simple delta over baseline.",
                "discarded_branches": ["branch-baseline", "branch-ablation"],
                "recommended_next_step": "write_draft",
                "audit_notes": ["integration proof chain selected branch-main"],
            }
        if task_kind in {"write_draft", "write_section"}:
            metrics = input_payload.get("metrics", {})
            accuracy = float(metrics.get("accuracy", 0.0))
            return {
                "title": f"Proof Draft {input_payload.get('branch_id', 'branch-main')}",
                "output_format": "markdown",
                "sections": [
                    {
                        "heading": "Results",
                        "markdown": f"The selected branch reaches {accuracy:.2f} accuracy under the deterministic proof setup.",
                        "supporting_claim_ids": input_payload.get("claim_ids", []),
                    }
                ],
                "citations": [],
                "audit_notes": ["integration proof chain generated grounded draft output"],
            }
        if task_kind in {"style_pass", "polish_draft"}:
            return {
                "revised_markdown": "# Styled Proof Draft\n\nThe deterministic proof chain completed successfully.\n",
                "change_notes": ["integration proof chain style pass"],
            }
        return await original_generate(self, system_prompt, user_input, tools, response_schema, model, provider_config)

    monkeypatch.setattr(LocalProvider, "generate", patched_generate)
    monkeypatch.setattr(
        client.app.state.research_guide_service,
        "_collect_seed_papers",
        lambda queries, max_papers: [
            {
                "title": "Proof Seed Paper",
                "abstract": "A durable seed paper for the integration proof chain.",
                "authors": ["Integration Author"],
                "published": "2025-01-01",
                "arxiv_id": "2501.00001",
            }
        ],
    )

    async def fake_decompose(goal: str) -> list[str]:
        return [goal]

    monkeypatch.setattr(client.app.state.research_guide_service, "_decompose_queries", fake_decompose)

    start_response = client.post(
        "/guide/start",
        json={
            "research_goal": "robust retrieval benchmark",
            "project_name": "Proof Chain",
            "owner": "integration",
            "max_papers": 1,
            "expected_min_papers": 1,
            "auto_dispatch": True,
        },
    )
    assert start_response.status_code == 200
    project_id = start_response.json()["project_id"]
    assert start_response.json()["autopilot"]["stop_reason"] == "human_select_ready"

    flow_after_start = client.get(f"/projects/{project_id}/flow")
    assert flow_after_start.status_code == 200
    assert flow_after_start.json()["stage"] == "HUMAN_SELECT"

    tasks = client.get("/tasks").json()
    human_select_task = next(
        task for task in tasks if task["project_id"] == project_id and task["kind"] == "human_select"
    )
    gap_id = human_select_task["input_payload"]["ranked_candidates"][0]["gap_id"]

    adopt_response = client.post(
        "/guide/adopt-direction",
        json={
            "project_id": project_id,
            "human_select_task_id": human_select_task["task_id"],
            "gap_id": gap_id,
            "research_question": "Can a branch-selected extension improve robust retrieval?",
            "operator_note": "Use the deterministic proof chain.",
            "owner": "integration",
            "auto_dispatch": False,
        },
    )
    assert adopt_response.status_code == 200

    stop_reason = ""
    for _ in range(4):
        autopilot_response = client.post(f"/projects/{project_id}/autopilot")
        assert autopilot_response.status_code == 200
        stop_reason = autopilot_response.json()["autopilot"]["stop_reason"]
        if stop_reason == "idle":
            break
    assert stop_reason == "idle"

    flow = client.get(f"/projects/{project_id}/flow").json()
    dashboard = client.get(f"/projects/{project_id}/dashboard").json()
    events = client.get(f"/projects/{project_id}/events?limit=200").json()
    branches = client.get(f"/projects/{project_id}/branches/compare").json()
    artifacts = client.get("/artifacts").json()
    results_freeze = client.get("/freezes/results").json()

    assert flow["stage"] == "SUBMISSION_READY"
    assert dashboard["run_count"] == 3
    assert dashboard["artifact_count"] >= 10
    assert dashboard["flow_snapshot"]["stage"] == "SUBMISSION_READY"
    assert dashboard["recommended_next_task_kind"] == "archive_research"
    assert {branch["branch_name"] for branch in branches["branches"]} == {
        "branch-baseline",
        "branch-main",
        "branch-ablation",
    }
    assert max(branch["primary_value"] for branch in branches["branches"]) == 0.91
    assert results_freeze["results_id"] == f"{project_id}-branch-results"
    assert any(event["event_type"] == "guide.started" for event in events)
    assert any(event["event_type"] == "guide.direction_adopted" for event in events)
    assert any(event["event_type"] == "checkpoint.saved" for event in events)
    assert any(event["event_type"] == "task.completed" for event in events)
    artifact_kinds = {artifact["kind"] for artifact in artifacts}
    assert "experiment_script" in artifact_kinds
    assert "execution_log" in artifact_kinds
    assert "result_summary" in artifact_kinds
    assert "draft_markdown" in artifact_kinds
    assert "citation_verification_report" in artifact_kinds
    assert "verified_metrics_registry" in artifact_kinds
    assert "metric_grounding_report" in artifact_kinds
    assert "styled_markdown" in artifact_kinds


def test_operator_benchmark_script_smoke(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    repo_root = tmp_path
    if not repo_root.exists():
        raise AssertionError("tmp_path should exist")

    process = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_operator_benchmark.py")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    payload = json.loads(process.stdout)
    assert payload["checkpoint_resume_available"] is True
    assert payload["branch_count"] == 2
    assert payload["best_branch"] == "branch-b"
    assert payload["best_primary_metric"] == "accuracy"


def _branch_specs() -> list[dict[str, object]]:
    return [
        {
            "branch_id": "branch-baseline",
            "title": "Baseline reproduction",
            "hypothesis": "Reproduce the baseline faithfully before extending it.",
            "datasets": ["proof-dataset"],
            "metrics": ["accuracy", "loss"],
            "feasibility": "high",
            "expected_gain": "Establish a trustworthy anchor.",
            "constraints": ["match the baseline budget"],
        },
        {
            "branch_id": "branch-main",
            "title": "Main extension",
            "hypothesis": "Apply the main idea as a single controlled delta over the baseline.",
            "datasets": ["proof-dataset"],
            "metrics": ["accuracy", "loss"],
            "feasibility": "medium",
            "expected_gain": "Primary novelty branch.",
            "constraints": ["single factor change"],
        },
        {
            "branch_id": "branch-ablation",
            "title": "Low-cost ablation",
            "hypothesis": "Measure whether the effect survives a cheaper configuration.",
            "datasets": ["proof-dataset"],
            "metrics": ["accuracy", "loss"],
            "feasibility": "high",
            "expected_gain": "Boundary-condition evidence.",
            "constraints": ["reduced compute"],
        },
    ]
