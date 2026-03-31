from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProviderSpecModel(BaseModel):
    provider_name: str
    model: str | None = None


class ModelProfileModel(BaseModel):
    profile_name: str
    provider_name: str | None = None
    model: str | None = None
    max_steps: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DispatchProfileModel(BaseModel):
    provider: ProviderSpecModel | None = None
    model_profile: ModelProfileModel | None = None
    max_steps: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderHealthSnapshotModel(BaseModel):
    provider_family: str
    state: str
    cli_installed: bool
    manually_disabled: bool = False
    failure_class: str | None = None
    detail: str = ""
    cooldown_seconds_remaining: int = 0


class ResolvedDispatchModel(BaseModel):
    provider_name: str
    provider_family: str | None = None
    model: str | None = None
    model_profile_name: str | None = None
    max_steps: int | None = None
    role_name: str | None = None
    capability_class: str | None = None
    candidate_models: dict[str, list[str]] = Field(default_factory=dict)
    fallback_chain: list[str] = Field(default_factory=list)
    decision_reason: str | None = None
    fallback_reason: str | None = None
    health_snapshots: list[ProviderHealthSnapshotModel] = Field(default_factory=list)
    sources: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    strategy_metadata: dict[str, Any] = Field(default_factory=dict)
