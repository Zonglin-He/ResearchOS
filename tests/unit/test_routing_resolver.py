from app.routing.models import AgentRoutingPolicy, DispatchProfile, ModelProfile, ProviderSpec
from app.routing.resolver import RoutingResolver
from app.schemas.project import Project
from app.schemas.task import Task


def test_routing_resolver_applies_task_project_system_agent_precedence() -> None:
    resolver = RoutingResolver(
        DispatchProfile(
            provider=ProviderSpec(provider_name="claude", model="sonnet"),
            max_steps=12,
        )
    )
    project = Project(
        project_id="p1",
        name="ResearchOS",
        description="routing",
        status="active",
        dispatch_profile=DispatchProfile(
            provider=ProviderSpec(provider_name="gemini", model="gemini-2.5-pro"),
            max_steps=24,
        ),
    )
    task = Task(
        task_id="t1",
        project_id="p1",
        kind="paper_ingest",
        goal="read",
        input_payload={},
        owner="tester",
        dispatch_profile=DispatchProfile(
            provider=ProviderSpec(provider_name="codex", model="gpt-5.4"),
            max_steps=32,
        ),
    )
    policy = AgentRoutingPolicy(
        agent_name="reader_agent",
        fallback_provider=ProviderSpec(provider_name="local", model="gpt-5.4-mini"),
    )

    resolved = resolver.resolve(task=task, project=project, agent_policy=policy)

    assert resolved.provider_name == "codex"
    assert resolved.model == "gpt-5.4"
    assert resolved.max_steps == 32
    assert resolved.sources["provider_name"] == "task_override"
    assert resolved.sources["model"] == "task_override"
    assert resolved.sources["max_steps"] == "task_override"


def test_routing_resolver_uses_agent_fallback_when_higher_layers_missing() -> None:
    resolver = RoutingResolver(DispatchProfile())
    task = Task(
        task_id="t1",
        project_id="p1",
        kind="paper_ingest",
        goal="read",
        input_payload={},
        owner="tester",
    )
    policy = AgentRoutingPolicy(
        agent_name="reader_agent",
        fallback_provider=ProviderSpec(provider_name="claude", model="haiku"),
        fallback_model_profile=ModelProfile(
            profile_name="reader-fallback",
            provider_name="claude",
            model="haiku",
            max_steps=6,
        ),
    )

    resolved = resolver.resolve(task=task, project=None, agent_policy=policy)

    assert resolved.provider_name == "claude"
    assert resolved.model == "haiku"
    assert resolved.max_steps == 6
    assert resolved.model_profile_name == "reader-fallback"
    assert resolved.sources["provider_name"] == "agent_fallback"
