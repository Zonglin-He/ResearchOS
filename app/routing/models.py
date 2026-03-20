from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


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
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolvedDispatch:
    provider_name: str
    model: str | None = None
    model_profile_name: str | None = None
    max_steps: int | None = None
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
        model=model,
        model_profile_name=model_profile_name,
        max_steps=max_steps,
        sources=dict(data.get("sources") or {}),
        metadata=dict(data.get("metadata") or {}),
    )
