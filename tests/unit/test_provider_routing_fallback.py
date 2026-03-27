import asyncio
from pathlib import Path

from app.agents.llm_agent import PromptDrivenAgent
from app.providers.base import BaseProvider
from app.providers.health import ProviderHealthService
from app.providers.registry import ProviderRegistry
from app.routing.models import (
    AgentRoutingPolicy,
    DispatchProfile,
    FallbackChain,
    ProviderFamily,
    ProviderSpec,
    RoleRoutingPolicy,
    RoutingDecisionReason,
)
from app.routing.provider_router import ProviderInvocationService
from app.routing.resolver import RoutingResolver
from app.schemas.context import RunContext
from app.schemas.result import AgentResult
from app.schemas.task import Task


REPO_ROOT = Path(__file__).resolve().parents[2]


class FailingProvider(BaseProvider):
    def __init__(self, message: str) -> None:
        self.message = message

    async def generate(self, system_prompt, user_input, tools=None, response_schema=None, model=None) -> dict:
        raise RuntimeError(self.message)


class StaticProvider(BaseProvider):
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def generate(self, system_prompt, user_input, tools=None, response_schema=None, model=None) -> dict:
        return self.payload


class MinimalAgent(PromptDrivenAgent):
    name = "minimal_agent"
    description = "Minimal prompt-driven agent for routing tests."
    prompt_path = str(REPO_ROOT / "prompts" / "reviewer.md")

    def build_result(self, task: Task, ctx, output: dict) -> AgentResult:
        return AgentResult(status="success", output=output)


def test_provider_health_service_classifies_rate_limit_and_exhaustion() -> None:
    registry = ProviderRegistry()
    registry.register("claude", lambda: StaticProvider({}))
    health = ProviderHealthService(cooldown_seconds=60)

    rate_limited = health.classify_failure("claude", RuntimeError("rate limit exceeded"), registry)
    exhausted = health.classify_failure("claude", RuntimeError("quota exhausted"), registry)

    assert rate_limited.state == "rate_limited"
    assert rate_limited.failure_class == "rate_limit"
    assert exhausted.state == "exhausted"
    assert exhausted.failure_class == "quota_exhaustion"


def test_provider_health_service_summarizes_large_provider_errors() -> None:
    registry = ProviderRegistry()
    registry.register("codex", lambda: StaticProvider({}))
    health = ProviderHealthService(cooldown_seconds=60)

    error = RuntimeError(
        "codex provider failed: OpenAI Codex v0.111.0 (research preview) workdir: C:\\Anti Project\\ResearchOS "
        "<role_contract> huge hidden payload that should not leak to provider health cards"
    )

    snapshot = health.classify_failure("codex", error, registry)

    assert snapshot.failure_class == "process_failure"
    assert snapshot.detail.startswith("codex provider failed: OpenAI Codex v0.111.0")
    assert "workdir:" not in snapshot.detail
    assert "<role_contract>" not in snapshot.detail


def test_routing_resolver_uses_role_defaults_for_librarian_and_executor() -> None:
    resolver = RoutingResolver(
        DispatchProfile(
            provider=ProviderSpec(provider_name="claude", model="sonnet"),
            metadata={"source": "implicit_default"},
        )
    )
    librarian_policy = AgentRoutingPolicy(
        agent_name="reader_agent",
        default_role_policy=RoleRoutingPolicy(
            role_name="librarian",
            capability_class="retrieval",
            family_priority=["gemini", "claude", "codex", "local"],
            family_model_priority={"gemini": ["gemini-auto", "gemini-pro"]},
            fallback_chain=FallbackChain(["gemini", "claude", "codex", "local"]),
        ),
    )
    executor_policy = AgentRoutingPolicy(
        agent_name="builder_agent",
        default_role_policy=RoleRoutingPolicy(
            role_name="executor",
            capability_class="execution",
            family_priority=["codex", "claude", "local"],
            family_model_priority={"codex": ["gpt-5.3-codex", "gpt-5.4"]},
            fallback_chain=FallbackChain(["codex", "claude", "local"]),
        ),
    )

    librarian_task = Task(
        task_id="t-reader",
        project_id="p1",
        kind="paper_ingest",
        goal="read",
        input_payload={},
        owner="tester",
    )
    executor_task = Task(
        task_id="t-builder",
        project_id="p1",
        kind="implement_experiment",
        goal="run",
        input_payload={},
        owner="tester",
    )

    librarian_dispatch = resolver.resolve(task=librarian_task, project=None, agent_policy=librarian_policy)
    executor_dispatch = resolver.resolve(task=executor_task, project=None, agent_policy=executor_policy)

    assert librarian_dispatch.provider_name == "gemini"
    assert librarian_dispatch.fallback_chain == ["gemini", "claude", "codex", "local"]
    assert librarian_dispatch.role_name == "librarian"
    assert executor_dispatch.provider_name == "codex"
    assert executor_dispatch.fallback_chain == ["codex", "claude", "local"]
    assert executor_dispatch.role_name == "executor"


def test_prompt_driven_agent_falls_back_when_claude_rate_limited() -> None:
    registry = ProviderRegistry()
    registry.register("claude", lambda: FailingProvider("rate limit exceeded"))
    registry.register("codex", lambda: StaticProvider({"summary": "fallback success"}))
    registry.register("local", lambda: StaticProvider({"summary": "local success"}))

    health = ProviderHealthService(cooldown_seconds=60)
    invocation_service = ProviderInvocationService(registry, health)
    agent = MinimalAgent(
        StaticProvider({"summary": "unused"}),
        provider_registry=registry,
        provider_invocation_service=invocation_service,
        routing_policy=AgentRoutingPolicy(
            agent_name="minimal_agent",
            default_role_policy=RoleRoutingPolicy(
                role_name="reviewer",
                capability_class="review",
                family_priority=["claude", "codex", "gemini", "local"],
                family_model_priority={
                    "claude": ["sonnet"],
                    "codex": ["gpt-5.4"],
                    "local": ["deterministic-reader"],
                },
                fallback_chain=FallbackChain(["claude", "codex", "local"]),
            ),
        ),
    )
    task = Task(
        task_id="t1",
        project_id="p1",
        kind="review_build",
        goal="review",
        input_payload={},
        owner="tester",
    )
    ctx = RunContext(
        run_id="run-t1",
        project_id="p1",
        task_id="t1",
        routing=RoutingResolver(
            DispatchProfile(
                provider=ProviderSpec(provider_name="claude", model="sonnet"),
                metadata={"source": "implicit_default"},
            )
        ).resolve(
            task=task,
            project=None,
            agent_policy=agent.routing_policy,
        ),
    )

    result = asyncio.run(agent.run(task, ctx))

    assert result.output["summary"] == "fallback success"
    assert ctx.routing is not None
    assert ctx.routing.provider_name == "codex"
    assert ctx.routing.fallback_reason == RoutingDecisionReason.RATE_LIMIT_FALLBACK.value
    assert ctx.routing.health_snapshots[0].state == "rate_limited"


def test_explicit_system_provider_still_overrides_role_default() -> None:
    resolver = RoutingResolver(
        DispatchProfile(
            provider=ProviderSpec(provider_name="local", model="deterministic-reader"),
            metadata={"source": "env_explicit"},
        )
    )
    policy = AgentRoutingPolicy(
        agent_name="reader_agent",
        default_role_policy=RoleRoutingPolicy(
            role_name="librarian",
            capability_class="retrieval",
            family_priority=["gemini", "claude", "codex", "local"],
            family_model_priority={"gemini": ["gemini-auto"]},
            fallback_chain=FallbackChain(["gemini", "claude", "codex", "local"]),
        ),
    )
    task = Task(
        task_id="t2",
        project_id="p1",
        kind="paper_ingest",
        goal="read",
        input_payload={},
        owner="tester",
    )

    resolved = resolver.resolve(task=task, project=None, agent_policy=policy)

    assert resolved.provider_name == ProviderFamily.LOCAL.value
    assert resolved.decision_reason == RoutingDecisionReason.SYSTEM_DEFAULT.value
