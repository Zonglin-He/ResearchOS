from fastapi.testclient import TestClient

import app.bootstrap as bootstrap_module
from app.api.app import create_app
from app.providers.base import BaseProvider
from app.providers.registry import ProviderRegistry


class StaticWorkflowProvider(BaseProvider):
    async def generate(
        self,
        system_prompt: str,
        user_input: str,
        tools=None,
        response_schema=None,
        model=None,
    ) -> dict:
        return {
            "paper_cards": [
                {
                    "paper_id": "paper-int-1",
                    "title": "Integration Paper",
                    "problem": "Weak grounding in streaming retrieval",
                    "setting": "streaming retrieval",
                    "task_type": "retrieval",
                    "evidence_refs": [{"section": "summary", "page": 1}],
                }
            ],
            "artifact_notes": ["reader extracted structured notes"],
            "uncertainties": ["full pdf unavailable"],
            "audit_notes": ["integration dispatch completed"],
        }


def build_static_provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    for provider_name in ("claude", "codex", "gemini", "local"):
        registry.register(provider_name, StaticWorkflowProvider)
    return registry


def test_dispatch_workflow_via_api_resolves_profile_and_persists_registry_outputs(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bootstrap_module, "build_provider_registry", build_static_provider_registry)
    client = TestClient(create_app(str(tmp_path / "researchos.db")))

    project_response = client.post(
        "/projects",
        json={
            "project_id": "p1",
            "name": "Integration Project",
            "description": "dispatch workflow integration test",
            "status": "active",
            "dispatch_profile": {
                "provider": {"provider_name": "claude", "model": "sonnet"},
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
                "provider": {"provider_name": "codex", "model": "gpt-5.4"},
                "max_steps": 18,
            },
        },
    )
    assert task_response.status_code == 200

    dispatch_response = client.post("/tasks/t1/dispatch")
    assert dispatch_response.status_code == 200
    assert dispatch_response.json()["status"] == "succeeded"
    assert dispatch_response.json()["last_run_routing"]["provider_name"] == "codex"
    assert dispatch_response.json()["last_run_routing"]["model"] == "gpt-5.4"

    task_read = client.get("/tasks/t1")
    paper_cards = client.get("/paper-cards")
    artifacts = client.get("/artifacts")

    assert task_read.status_code == 200
    assert task_read.json()["last_run_routing"]["provider_name"] == "codex"
    assert paper_cards.status_code == 200
    assert paper_cards.json()[0]["paper_id"] == "paper-int-1"
    assert artifacts.status_code == 200
    assert artifacts.json()[0]["kind"] == "reader_note"
    assert artifacts.json()[0]["run_id"] == "run-t1"
