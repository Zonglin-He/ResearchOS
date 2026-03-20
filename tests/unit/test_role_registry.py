from app.roles import (
    ROLE_REGISTRY,
    WorkflowRole,
    builder_role_binding,
    get_role_spec,
    reader_role_binding,
    role_routing_policy_for_role,
)


def test_role_registry_exposes_full_librarian_contract() -> None:
    spec = get_role_spec(WorkflowRole.LIBRARIAN)

    assert spec.role_id == WorkflowRole.LIBRARIAN
    assert spec.mission
    assert "source_material" in spec.required_inputs
    assert "paper_card" in spec.required_outputs
    assert spec.allowed_tools
    assert "experiment_runner" in spec.forbidden_tools
    assert spec.artifact_contracts[0].artifact_type == "paper_card"
    assert spec.default_capability_class.value == "retrieval"
    assert spec.default_provider_preference.family_priority[0] == "gemini"


def test_agent_role_bindings_resolve_role_specs_for_current_task_kinds() -> None:
    reader = reader_role_binding()
    builder = builder_role_binding()

    reader_librarian = reader.resolve_role_spec("paper_ingest")
    reader_scoper = reader.resolve_role_spec("read_source")
    builder_hypothesist = builder.resolve_role_spec("build_spec")
    builder_executor = builder.resolve_role_spec("implement_experiment")

    assert reader_librarian is not None
    assert reader_scoper is not None
    assert builder_hypothesist is not None
    assert builder_executor is not None
    assert reader_librarian.role_id == WorkflowRole.LIBRARIAN
    assert reader_scoper.role_id == WorkflowRole.SCOPER
    assert builder_hypothesist.role_id == WorkflowRole.HYPOTHESIST
    assert builder_executor.role_id == WorkflowRole.EXECUTOR
    assert reader.expected_artifact_types("paper_ingest") == ["paper_card"]
    assert builder.expected_artifact_types("implement_experiment") == ["run_manifest"]
    assert {spec.role_id for spec in builder.secondary_role_specs()} == {
        WorkflowRole.HYPOTHESIST,
        WorkflowRole.EXECUTOR,
    }


def test_role_routing_policy_is_derived_from_role_contract_preferences() -> None:
    reviewer_policy = role_routing_policy_for_role(WorkflowRole.REVIEWER)
    executor_policy = role_routing_policy_for_role(WorkflowRole.EXECUTOR)

    assert reviewer_policy.role_name == WorkflowRole.REVIEWER.value
    assert reviewer_policy.capability_class == "review"
    assert reviewer_policy.family_priority[:2] == ["claude", "codex"]
    assert reviewer_policy.family_model_priority["claude"] == ["sonnet"]
    assert executor_policy.role_name == WorkflowRole.EXECUTOR.value
    assert executor_policy.capability_class == "execution"
    assert executor_policy.family_priority == ["codex", "claude", "local"]
    assert executor_policy.family_model_priority["codex"] == ["gpt-5.3-codex", "gpt-5.4"]


def test_role_registry_returns_none_for_unknown_role_name() -> None:
    assert ROLE_REGISTRY.get("nonexistent") is None
