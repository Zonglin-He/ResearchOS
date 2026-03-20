import asyncio
import json

from app.providers.local_provider import LocalProvider


async def _generate(provider: LocalProvider, payload: dict, response_schema: dict | None = None) -> dict:
    return await provider.generate(
        system_prompt="local test",
        user_input=json.dumps(payload),
        response_schema=response_schema,
        model="deterministic-reader",
    )


def test_local_provider_builds_reader_output_from_source_summary() -> None:
    provider = LocalProvider()
    result = asyncio.run(
        _generate(
            provider,
            {
                "task": {
                    "task_id": "t1",
                    "kind": "paper_ingest",
                    "goal": "Read source",
                    "input_payload": {
                        "topic": "retrieval",
                        "source_summary": {
                            "title": "Local Integration Paper",
                            "abstract": "Compact local summary.",
                            "setting": "streaming retrieval",
                        },
                    },
                }
            },
        )
    )

    assert result["paper_cards"][0]["title"] == "Local Integration Paper"
    assert result["paper_cards"][0]["setting"] == "streaming retrieval"
    assert result["artifact_notes"] == ["local provider extracted notes for local-integration-paper"]


def test_local_provider_uses_explicit_fixture_override() -> None:
    provider = LocalProvider()
    fixture = {"decision": "pass", "summary": "fixture response"}

    result = asyncio.run(
        _generate(
            provider,
            {
                "task": {
                    "task_id": "t2",
                    "kind": "review_build",
                    "input_payload": {"local_provider_response": fixture},
                }
            },
        )
    )

    assert result == fixture


def test_local_provider_supports_analyst_verifier_and_archivist_tasks() -> None:
    provider = LocalProvider()

    analyst = asyncio.run(
        _generate(
            provider,
            {
                "task": {
                    "task_id": "t-analyst",
                    "kind": "analyze_results",
                    "input_payload": {"run_id": "run-1"},
                }
            },
        )
    )
    verifier = asyncio.run(
        _generate(
            provider,
            {
                "task": {
                    "task_id": "t-verifier",
                    "kind": "verify_evidence",
                    "input_payload": {"run_id": "run-1"},
                }
            },
        )
    )
    archivist = asyncio.run(
        _generate(
            provider,
            {
                "task": {
                    "task_id": "t-archivist",
                    "kind": "archive_research",
                    "input_payload": {},
                }
            },
        )
    )

    assert analyst["summary"] == "Deterministic analysis for run-1."
    assert verifier["recommendations"] == ["Inspect missing fields if verification is incomplete."]
    assert archivist["lessons"][0]["title"] == "Archive lesson for t-archivist"
