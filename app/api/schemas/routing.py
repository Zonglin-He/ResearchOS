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


class ResolvedDispatchModel(BaseModel):
    provider_name: str
    model: str | None = None
    model_profile_name: str | None = None
    max_steps: int | None = None
    sources: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
