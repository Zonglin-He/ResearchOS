from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ProviderFamily(str, Enum):
    CLAUDE = "claude"
    CODEX = "codex"
    GEMINI = "gemini"
    LOCAL = "local"


class ProviderAvailabilityState(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    RATE_LIMITED = "rate_limited"
    EXHAUSTED = "exhausted"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"


class ProviderFailureClass(str, Enum):
    AUTH_CONFIG = "auth_config"
    RATE_LIMIT = "rate_limit"
    QUOTA_EXHAUSTION = "quota_exhaustion"
    PROCESS_FAILURE = "process_failure"
    UNKNOWN_TRANSIENT = "unknown_transient"


class CapabilityClass(str, Enum):
    PLANNING = "planning"
    RETRIEVAL = "retrieval"
    SYNTHESIS = "synthesis"
    CODING = "coding"
    EXECUTION = "execution"
    REVIEW = "review"
    VERIFICATION = "verification"
    PUBLISHING = "publishing"
    ARCHIVAL = "archival"


class RoutingDecisionReason(str, Enum):
    TASK_OVERRIDE = "task_override"
    PROJECT_DEFAULT = "project_default"
    SYSTEM_DEFAULT = "system_default"
    ROLE_DEFAULT = "role_default"
    AGENT_FALLBACK = "agent_fallback"
    RATE_LIMIT_FALLBACK = "rate_limit_fallback"
    EXHAUSTION_FALLBACK = "exhaustion_fallback"
    HEALTH_FALLBACK = "health_fallback"
    LOCAL_DETERMINISTIC_FALLBACK = "local_deterministic_fallback"


@dataclass
class ProviderHealthSnapshot:
    provider_family: str
    state: str
    cli_installed: bool
    manually_disabled: bool = False
    failure_class: str | None = None
    detail: str = ""
    cooldown_seconds_remaining: int = 0


@dataclass
class FallbackChain:
    families: list[str] = field(default_factory=list)


@dataclass
class InvocationBudgetPolicy:
    prefer_low_cost: bool = True
    allow_expensive_upgrade: bool = False
    max_attempts_per_invocation: int = 4


@dataclass
class RoleRoutingPolicy:
    role_name: str
    capability_class: str
    family_priority: list[str] = field(default_factory=list)
    family_model_priority: dict[str, list[str]] = field(default_factory=dict)
    fallback_chain: FallbackChain = field(default_factory=FallbackChain)
    invocation_budget_policy: InvocationBudgetPolicy = field(default_factory=InvocationBudgetPolicy)


@dataclass
class ProviderSpec:
    provider_name: str
    model: str | None = None


@dataclass
class ModelProfile:
    profile_name: str
    provider_name: str | None = None
    model: str | None = None
    max_steps: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DispatchProfile:
    provider: ProviderSpec | None = None
    model_profile: ModelProfile | None = None
    max_steps: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRoutingPolicy:
    agent_name: str
    fallback_provider: ProviderSpec | None = None
    fallback_model_profile: ModelProfile | None = None
    default_role_policy: RoleRoutingPolicy | None = None
    task_kind_role_policies: dict[str, RoleRoutingPolicy] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def resolve_role_policy(self, task_kind: str) -> RoleRoutingPolicy | None:
        return self.task_kind_role_policies.get(task_kind, self.default_role_policy)


@dataclass
class ResolvedDispatch:
    provider_name: str
    provider_family: str | None = None
    model: str | None = None
    model_profile_name: str | None = None
    max_steps: int | None = None
    role_name: str | None = None
    capability_class: str | None = None
    candidate_models: dict[str, list[str]] = field(default_factory=dict)
    fallback_chain: list[str] = field(default_factory=list)
    decision_reason: str | None = None
    fallback_reason: str | None = None
    health_snapshots: list[ProviderHealthSnapshot] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def provider_spec_from_dict(data: Mapping[str, Any] | None) -> ProviderSpec | None:
    if not data:
        return None
    provider_name = data.get("provider_name") or data.get("provider")
    if not isinstance(provider_name, str) or not provider_name.strip():
        return None
    model = data.get("model")
    if model is not None and not isinstance(model, str):
        model = str(model)
    return ProviderSpec(provider_name=provider_name, model=model)


def model_profile_from_dict(data: Mapping[str, Any] | None) -> ModelProfile | None:
    if not data:
        return None
    profile_name = data.get("profile_name") or data.get("name")
    if not isinstance(profile_name, str) or not profile_name.strip():
        return None
    provider_name = data.get("provider_name") or data.get("provider")
    if provider_name is not None and not isinstance(provider_name, str):
        provider_name = str(provider_name)
    model = data.get("model")
    if model is not None and not isinstance(model, str):
        model = str(model)
    max_steps = data.get("max_steps")
    if max_steps is not None:
        max_steps = int(max_steps)
    metadata = data.get("metadata") or {}
    return ModelProfile(
        profile_name=profile_name,
        provider_name=provider_name,
        model=model,
        max_steps=max_steps,
        metadata=dict(metadata),
    )


def dispatch_profile_from_dict(data: Mapping[str, Any] | None) -> DispatchProfile | None:
    if not data:
        return None
    max_steps = data.get("max_steps")
    if max_steps is not None:
        max_steps = int(max_steps)
    metadata = data.get("metadata") or {}
    return DispatchProfile(
        provider=provider_spec_from_dict(data.get("provider")),
        model_profile=model_profile_from_dict(data.get("model_profile")),
        max_steps=max_steps,
        metadata=dict(metadata),
    )


def agent_routing_policy_from_dict(data: Mapping[str, Any] | None) -> AgentRoutingPolicy | None:
    if not data:
        return None
    agent_name = data.get("agent_name")
    if not isinstance(agent_name, str) or not agent_name.strip():
        return None
    metadata = data.get("metadata") or {}
    return AgentRoutingPolicy(
        agent_name=agent_name,
        fallback_provider=provider_spec_from_dict(data.get("fallback_provider")),
        fallback_model_profile=model_profile_from_dict(data.get("fallback_model_profile")),
        default_role_policy=role_routing_policy_from_dict(data.get("default_role_policy")),
        task_kind_role_policies={
            key: policy
            for key, value in dict(data.get("task_kind_role_policies") or {}).items()
            if (policy := role_routing_policy_from_dict(value)) is not None
        },
        metadata=dict(metadata),
    )


def resolved_dispatch_from_dict(data: Mapping[str, Any] | None) -> ResolvedDispatch | None:
    if not data:
        return None
    provider_name = data.get("provider_name")
    if not isinstance(provider_name, str) or not provider_name.strip():
        return None
    model = data.get("model")
    if model is not None and not isinstance(model, str):
        model = str(model)
    model_profile_name = data.get("model_profile_name")
    if model_profile_name is not None and not isinstance(model_profile_name, str):
        model_profile_name = str(model_profile_name)
    max_steps = data.get("max_steps")
    if max_steps is not None:
        max_steps = int(max_steps)
    return ResolvedDispatch(
        provider_name=provider_name,
        provider_family=_string_or_none(data.get("provider_family")) or provider_name,
        model=model,
        model_profile_name=model_profile_name,
        max_steps=max_steps,
        role_name=_string_or_none(data.get("role_name")),
        capability_class=_string_or_none(data.get("capability_class")),
        candidate_models={
            str(key): [str(item) for item in value]
            for key, value in dict(data.get("candidate_models") or {}).items()
            if isinstance(value, list)
        },
        fallback_chain=[str(item) for item in data.get("fallback_chain", [])],
        decision_reason=_string_or_none(data.get("decision_reason")),
        fallback_reason=_string_or_none(data.get("fallback_reason")),
        health_snapshots=[
            snapshot
            for item in data.get("health_snapshots", [])
            if (snapshot := provider_health_snapshot_from_dict(item)) is not None
        ],
        sources=dict(data.get("sources") or {}),
        metadata=dict(data.get("metadata") or {}),
    )


def provider_health_snapshot_from_dict(
    data: Mapping[str, Any] | None,
) -> ProviderHealthSnapshot | None:
    if not data:
        return None
    provider_family = _string_or_none(data.get("provider_family"))
    state = _string_or_none(data.get("state"))
    if provider_family is None or state is None:
        return None
    return ProviderHealthSnapshot(
        provider_family=provider_family,
        state=state,
        cli_installed=bool(data.get("cli_installed", False)),
        manually_disabled=bool(data.get("manually_disabled", False)),
        failure_class=_string_or_none(data.get("failure_class")),
        detail=_string_or_none(data.get("detail")) or "",
        cooldown_seconds_remaining=int(data.get("cooldown_seconds_remaining", 0)),
    )


def role_routing_policy_from_dict(data: Mapping[str, Any] | None) -> RoleRoutingPolicy | None:
    if not data:
        return None
    role_name = _string_or_none(data.get("role_name"))
    capability_class = _string_or_none(data.get("capability_class"))
    if role_name is None or capability_class is None:
        return None
    budget = invocation_budget_policy_from_dict(data.get("invocation_budget_policy"))
    fallback_chain = fallback_chain_from_dict(data.get("fallback_chain"))
    return RoleRoutingPolicy(
        role_name=role_name,
        capability_class=capability_class,
        family_priority=[str(item) for item in data.get("family_priority", [])],
        family_model_priority={
            str(key): [str(item) for item in value]
            for key, value in dict(data.get("family_model_priority") or {}).items()
            if isinstance(value, list)
        },
        fallback_chain=fallback_chain or FallbackChain(),
        invocation_budget_policy=budget or InvocationBudgetPolicy(),
    )


def fallback_chain_from_dict(data: Mapping[str, Any] | list[Any] | None) -> FallbackChain | None:
    if data is None:
        return None
    if isinstance(data, list):
        return FallbackChain(families=[str(item) for item in data])
    families = data.get("families")
    if not isinstance(families, list):
        return None
    return FallbackChain(families=[str(item) for item in families])


def invocation_budget_policy_from_dict(
    data: Mapping[str, Any] | None,
) -> InvocationBudgetPolicy | None:
    if not data:
        return None
    return InvocationBudgetPolicy(
        prefer_low_cost=bool(data.get("prefer_low_cost", True)),
        allow_expensive_upgrade=bool(data.get("allow_expensive_upgrade", False)),
        max_attempts_per_invocation=int(data.get("max_attempts_per_invocation", 4)),
    )


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)
