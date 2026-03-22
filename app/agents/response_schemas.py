from __future__ import annotations


READER_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "paper_cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "paper_id": {"type": "string"},
                    "title": {"type": "string"},
                    "problem": {"type": "string"},
                    "setting": {"type": "string"},
                    "task_type": {"type": "string"},
                    "core_assumption": {"type": "array", "items": {"type": "string"}},
                    "method_summary": {"type": "string"},
                    "key_modules": {"type": "array", "items": {"type": "string"}},
                    "datasets": {"type": "array", "items": {"type": "string"}},
                    "metrics": {"type": "array", "items": {"type": "string"}},
                    "strongest_result": {"type": "string"},
                    "claimed_contributions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "hidden_dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "likely_failure_modes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "repro_risks": {"type": "array", "items": {"type": "string"}},
                    "idea_seeds": {"type": "array", "items": {"type": "string"}},
                    "evidence_refs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "section": {"type": "string"},
                                "page": {"type": "integer"},
                            },
                            "required": ["section", "page"],
                        },
                    },
                },
                "required": ["paper_id", "title", "problem", "setting", "task_type"],
            },
        },
        "artifact_notes": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "audit_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["paper_cards"],
}

MAPPER_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "gap_map": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "clusters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "gaps": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "gap_id": {"type": "string"},
                                        "description": {"type": "string"},
                                        "supporting_papers": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "evidence_summary": {"type": "string"},
                                        "attack_surface": {"type": "string"},
                                        "difficulty": {"type": "string"},
                                        "novelty_type": {"type": "string"},
                                        "feasibility": {"type": "string"},
                                        "novelty_score": {"type": "number"},
                                    },
                                    "required": ["gap_id", "description"],
                                },
                            },
                        },
                        "required": ["name", "gaps"],
                    },
                },
            },
            "required": ["topic", "clusters"],
        },
        "ranked_candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gap_id": {"type": "string"},
                    "score": {"type": "number"},
                    "rationale": {"type": "string"},
                    "feasibility": {"type": "string"},
                    "novelty_score": {"type": "number"},
                    "evidence_summary": {"type": "string"},
                },
                "required": ["gap_id", "score", "rationale"],
            },
        },
        "audit_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["gap_map", "ranked_candidates"],
}

BUILDER_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "experiment_script": {"type": "string"},
        "execution_command": {"type": "string"},
        "artifacts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "artifact_id": {"type": "string"},
                    "kind": {"type": "string"},
                    "path": {"type": "string"},
                    "hash": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["artifact_id", "kind", "path", "hash"],
            },
        },
        "run_manifest": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "spec_id": {"type": "string"},
                "git_commit": {"type": "string"},
                "config_hash": {"type": "string"},
                "dataset_snapshot": {"type": "string"},
                "seed": {"type": "integer"},
                "gpu": {"type": "string"},
                "status": {"type": "string"},
                "metrics": {"type": "object"},
                "artifacts": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "run_id",
                "spec_id",
                "git_commit",
                "config_hash",
                "dataset_snapshot",
                "seed",
                "gpu",
            ],
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string"},
                    "text": {"type": "string"},
                    "claim_type": {"type": "string"},
                    "supported_by_tables": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "risk_level": {"type": "string"},
                },
                "required": ["claim_id", "text", "claim_type"],
            },
        },
        "audit_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "run_manifest"],
}

REVIEWER_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["pass", "needs_revision", "needs_approval", "reject"],
        },
        "summary": {"type": "string"},
        "blocking_issues": {"type": "array", "items": {"type": "string"}},
        "audit_notes": {"type": "array", "items": {"type": "string"}},
        "claim_updates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string"},
                    "approved_by_human": {"type": "boolean"},
                    "risk_level": {"type": "string"},
                },
                "required": ["claim_id"],
            },
        },
    },
    "required": ["decision", "summary"],
}

WRITER_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "markdown": {"type": "string"},
                    "supporting_claim_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["heading", "markdown"],
            },
        },
        "audit_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "sections"],
}

STYLE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "revised_markdown": {"type": "string"},
        "change_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["revised_markdown"],
}

ANALYST_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "metrics": {"type": "object"},
        "execution_success": {"type": "boolean"},
        "anomalies": {"type": "array", "items": {"type": "string"}},
        "recommended_actions": {"type": "array", "items": {"type": "string"}},
        "audit_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary"],
}

VERIFIER_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "recommendations": {"type": "array", "items": {"type": "string"}},
        "audit_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary"],
}

ARCHIVIST_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "lessons": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "recommended_action": {"type": "string"},
                    "lesson_kind": {"type": "string"},
                    "failure_type": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "summary"],
            },
        },
        "provenance_notes": {"type": "array", "items": {"type": "string"}},
        "audit_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary"],
}
