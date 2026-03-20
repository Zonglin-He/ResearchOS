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
