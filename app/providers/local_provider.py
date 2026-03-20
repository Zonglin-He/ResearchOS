from __future__ import annotations

import json
from typing import Any

from app.providers.base import BaseProvider


class LocalProvider(BaseProvider):
    async def generate(
        self,
        system_prompt: str,
        user_input: str,
        tools: list[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        payload = self._parse_user_input(user_input)
        guide_request = payload.get("guide_request")
        if isinstance(guide_request, dict) and guide_request:
            return self._guide_response(guide_request)
        task_payload = payload.get("task", {})
        input_payload = task_payload.get("input_payload", {})

        fixture = input_payload.get("local_provider_response") or input_payload.get("mock_response")
        if isinstance(fixture, dict):
            return fixture

        task_kind = task_payload.get("kind", "")
        if task_kind in {"paper_ingest", "repo_ingest", "read_source"}:
            return self._reader_response(task_payload)
        if task_kind in {"gap_mapping", "map_gaps"}:
            return self._mapper_response(task_payload)
        if task_kind in {"build_spec", "implement_experiment", "reproduce_baseline"}:
            return self._builder_response(task_payload)
        if task_kind in {"analyze_results", "analyze_run"}:
            return self._analyst_response(task_payload)
        if task_kind in {"verify_evidence", "verify_claim", "verify_results"}:
            return self._verifier_response(task_payload)
        if task_kind in {"archive_research", "archive_run", "record_lessons"}:
            return self._archivist_response(task_payload)
        if task_kind in {"review_build", "audit_run"}:
            return self._reviewer_response(task_payload)
        if task_kind in {"write_draft", "write_section"}:
            return self._writer_response(task_payload)
        if task_kind in {"style_pass", "polish_draft"}:
            return self._style_response(task_payload)
        if response_schema is not None:
            materialized = self._materialize_from_schema(response_schema)
            return materialized if isinstance(materialized, dict) else {"content": materialized}
        return {"content": "local provider response"}

    def _guide_response(self, guide_request: dict[str, Any]) -> dict[str, Any]:
        heuristic = guide_request.get("heuristic_recommendation", {})
        recommended_task_kind = heuristic.get("recommended_task_kind", "paper_ingest")
        recommendation_reason = heuristic.get(
            "recommendation_reason",
            "This is the safest bounded step for the current project state.",
        )
        expected_artifact = heuristic.get("expected_artifact", "workflow artifact")
        likely_next_task_kind = heuristic.get("likely_next_task_kind")
        research_goal = guide_request.get("research_goal", "")
        project = guide_request.get("project", {}) if isinstance(guide_request.get("project"), dict) else {}
        suggested_project_name = heuristic.get("suggested_project_name") or project.get("name") or "ResearchOS Project"
        suggested_project_description = (
            heuristic.get("suggested_project_description")
            or project.get("description")
            or research_goal
            or "Guided ResearchOS project."
        )
        suggested_task_goal = heuristic.get("suggested_task_goal") or research_goal or suggested_project_description
        mode = guide_request.get("mode", "first_project")

        if mode == "existing_project":
            assistant_message = (
                f"I reviewed the current project state. I recommend {recommended_task_kind} next because "
                f"{recommendation_reason} Finish it to produce {expected_artifact}."
            )
            follow_up_prompt = "If you want, I can help you create that task next."
            summary = (
                "Stay in the current project container and move it forward one bounded task at a time."
            )
        else:
            assistant_message = (
                f"Based on your research goal, start with {recommended_task_kind}. "
                f"{recommendation_reason} That should give you a first durable artifact: {expected_artifact}."
            )
            follow_up_prompt = (
                "I can help you create the project container now. Accept the suggested name or replace it."
            )
            summary = (
                "Create the project container first, then create one bounded initial task and dispatch it."
            )

        return {
            "assistant_message": assistant_message,
            "summary": summary,
            "follow_up_prompt": follow_up_prompt,
            "recommended_task_kind": recommended_task_kind,
            "recommendation_reason": recommendation_reason,
            "expected_artifact": expected_artifact,
            "likely_next_task_kind": likely_next_task_kind,
            "suggested_project_name": suggested_project_name,
            "suggested_project_description": suggested_project_description,
            "suggested_task_goal": suggested_task_goal,
        }

    @staticmethod
    def _parse_user_input(user_input: str) -> dict[str, Any]:
        try:
            payload = json.loads(user_input)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _reader_response(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        input_payload = task_payload.get("input_payload", {})
        source_summary = input_payload.get("source_summary", {})
        topic = input_payload.get("topic", "research")
        title = source_summary.get("title") or task_payload.get("goal") or "Local Provider Source"
        abstract = source_summary.get("abstract", "") or f"Compact summary for {topic}."
        setting = source_summary.get("setting", "") or topic or "unspecified setting"
        paper_id = source_summary.get("paper_id") or title.lower().replace(" ", "-")[:32] or task_payload.get("task_id", "paper-local")
        return {
            "paper_cards": [
                {
                    "paper_id": paper_id,
                    "title": title,
                    "problem": abstract,
                    "setting": setting,
                    "task_type": source_summary.get("task_type", topic or "research"),
                    "method_summary": abstract,
                    "datasets": source_summary.get("datasets", []),
                    "metrics": source_summary.get("metrics", []),
                    "idea_seeds": [topic] if topic else [],
                    "evidence_refs": [{"section": "source_summary", "page": 1}],
                }
            ],
            "artifact_notes": [f"local provider extracted notes for {paper_id}"],
            "uncertainties": ["local provider used source_summary fallback"],
            "audit_notes": ["local provider generated deterministic reader output"],
        }

    def _mapper_response(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        input_payload = task_payload.get("input_payload", {})
        topic = input_payload.get("topic", "research topic")
        paper_ids = input_payload.get("paper_ids", [])
        gap_id = f"{topic or 'topic'}-gap-1".replace(" ", "-")
        return {
            "gap_map": {
                "topic": topic,
                "clusters": [
                    {
                        "name": "Deterministic Gap Cluster",
                        "gaps": [
                            {
                                "gap_id": gap_id,
                                "description": f"Investigate an unexplored extension for {topic}.",
                                "supporting_papers": paper_ids,
                                "attack_surface": topic,
                                "difficulty": "medium",
                                "novelty_type": "extension",
                            }
                        ],
                    }
                ],
            },
            "ranked_candidates": [
                {
                    "gap_id": gap_id,
                    "score": 1.0,
                    "rationale": f"Deterministic local-provider ranking for {topic}.",
                }
            ],
            "audit_notes": ["local provider generated deterministic mapper output"],
        }

    def _builder_response(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        task_id = task_payload.get("task_id", "task")
        input_payload = task_payload.get("input_payload", {})
        spec_id = input_payload.get("spec_id", "spec-local")
        run_id = f"run-{task_id}"
        artifact_id = f"{run_id}-checkpoint"
        return {
            "summary": "Local provider produced a deterministic experiment summary.",
            "artifacts": [
                {
                    "artifact_id": artifact_id,
                    "kind": "checkpoint",
                    "path": f"artifacts/{run_id}/{artifact_id}.bin",
                    "hash": "local-checkpoint-hash",
                    "metadata": {"provider": "local"},
                }
            ],
            "run_manifest": {
                "run_id": run_id,
                "spec_id": spec_id,
                "git_commit": "local-git-commit",
                "config_hash": "local-config-hash",
                "dataset_snapshot": input_payload.get("dataset_snapshot", "local-dataset"),
                "seed": 0,
                "gpu": "cpu",
                "status": "completed",
                "metrics": {"score": 0.5},
                "artifacts": [artifact_id],
            },
            "claims": [
                {
                    "claim_id": f"claim-{task_id}",
                    "text": "Local provider baseline claim.",
                    "claim_type": "result",
                    "supported_by_tables": [],
                    "risk_level": "low",
                }
            ],
            "audit_notes": ["local provider generated deterministic builder output"],
        }

    def _reviewer_response(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "decision": "pass",
            "summary": f"Local provider review passed for {task_payload.get('task_id', 'task')}.",
            "blocking_issues": [],
            "audit_notes": ["local provider generated deterministic reviewer output"],
            "claim_updates": [],
        }

    def _analyst_response(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        run_id = task_payload.get("input_payload", {}).get("run_id", "run-local")
        return {
            "summary": f"Deterministic analysis for {run_id}.",
            "anomalies": [f"No severe anomalies detected for {run_id}."],
            "recommended_actions": ["Review metrics drift against baseline."],
            "audit_notes": ["local provider generated deterministic analyst output"],
        }

    def _verifier_response(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "summary": "Deterministic verification summary from the local provider.",
            "recommendations": ["Inspect missing fields if verification is incomplete."],
            "audit_notes": ["local provider generated deterministic verifier output"],
        }

    def _archivist_response(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        task_id = task_payload.get("task_id", "task")
        return {
            "summary": f"Deterministic archive summary for {task_id}.",
            "lessons": [
                {
                    "title": f"Archive lesson for {task_id}",
                    "summary": "Record the key execution assumptions before the next run.",
                    "recommended_action": "Capture baseline comparison context.",
                    "lesson_kind": "lesson",
                    "failure_type": "",
                    "evidence_refs": [f"task:{task_id}"],
                }
            ],
            "provenance_notes": ["Deterministic archival note linked to the task."],
            "audit_notes": ["local provider generated deterministic archivist output"],
        }

    def _writer_response(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        title = task_payload.get("goal") or "ResearchOS Draft"
        return {
            "title": title,
            "sections": [
                {
                    "heading": "Introduction",
                    "markdown": "This draft was generated by the deterministic local provider.",
                    "supporting_claim_ids": [],
                }
            ],
            "audit_notes": ["local provider generated deterministic writer output"],
        }

    def _style_response(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "revised_markdown": "# Styled Draft\n\nThis draft was polished by the local provider.\n",
            "change_notes": ["local provider applied deterministic style pass"],
        }

    def _materialize_from_schema(self, schema: dict[str, Any]) -> Any:
        schema_type = schema.get("type")
        if "enum" in schema:
            return schema["enum"][0]
        if schema_type == "object":
            properties = schema.get("properties", {})
            required = schema.get("required", list(properties))
            return {
                key: self._materialize_from_schema(properties[key])
                for key in required
                if key in properties
            }
        if schema_type == "array":
            item_schema = schema.get("items", {"type": "string"})
            return [self._materialize_from_schema(item_schema)]
        if schema_type == "integer":
            return 0
        if schema_type == "number":
            return 0.0
        if schema_type == "boolean":
            return False
        return "local-provider-value"
