from __future__ import annotations

from app.routing.models import (
    AgentRoutingPolicy,
    DispatchProfile,
    ResolvedDispatch,
)
from app.schemas.project import Project
from app.schemas.task import Task


class RoutingResolver:
    def __init__(self, system_default: DispatchProfile) -> None:
        self.system_default = system_default

    def resolve(
        self,
        *,
        task: Task,
        project: Project | None,
        agent_policy: AgentRoutingPolicy | None,
    ) -> ResolvedDispatch:
        task_profile = task.dispatch_profile
        project_profile = project.dispatch_profile if project is not None else None
        system_profile = self.system_default

        provider_name, provider_source = self._resolve_provider_name(
            task_profile,
            project_profile,
            system_profile,
            agent_policy,
        )
        if provider_name is None:
            raise ValueError(
                f"Unable to resolve provider for task {task.task_id} and agent "
                f"{agent_policy.agent_name if agent_policy else '<unknown>'}"
            )

        model, model_source = self._resolve_model(
            task_profile,
            project_profile,
            system_profile,
            agent_policy,
        )
        max_steps, max_steps_source = self._resolve_max_steps(
            task_profile,
            project_profile,
            system_profile,
            agent_policy,
        )
        model_profile_name = self._resolve_model_profile_name(
            task_profile,
            project_profile,
            system_profile,
            agent_policy,
        )

        metadata: dict[str, object] = {}
        for profile in (
            self._profile_from_policy(agent_policy),
            system_profile,
            project_profile,
            task_profile,
        ):
            if profile is None:
                continue
            metadata.update(profile.metadata)

        return ResolvedDispatch(
            provider_name=provider_name,
            model=model,
            model_profile_name=model_profile_name,
            max_steps=max_steps,
            sources={
                "provider_name": provider_source,
                "model": model_source,
                "max_steps": max_steps_source,
            },
            metadata=metadata,
        )

    @staticmethod
    def _profile_from_policy(policy: AgentRoutingPolicy | None) -> DispatchProfile | None:
        if policy is None:
            return None
        return DispatchProfile(
            provider=policy.fallback_provider,
            model_profile=policy.fallback_model_profile,
            metadata={"agent_name": policy.agent_name, **policy.metadata},
        )

    def _resolve_provider_name(
        self,
        task_profile: DispatchProfile | None,
        project_profile: DispatchProfile | None,
        system_profile: DispatchProfile | None,
        agent_policy: AgentRoutingPolicy | None,
    ) -> tuple[str | None, str]:
        for source_name, profile in (
            ("task_override", task_profile),
            ("project_default", project_profile),
            ("system_default", system_profile),
            ("agent_fallback", self._profile_from_policy(agent_policy)),
        ):
            provider_name = self._provider_name_from_profile(profile)
            if provider_name is not None:
                return provider_name, source_name
        return None, "unresolved"

    def _resolve_model(
        self,
        task_profile: DispatchProfile | None,
        project_profile: DispatchProfile | None,
        system_profile: DispatchProfile | None,
        agent_policy: AgentRoutingPolicy | None,
    ) -> tuple[str | None, str]:
        for source_name, profile in (
            ("task_override", task_profile),
            ("project_default", project_profile),
            ("system_default", system_profile),
            ("agent_fallback", self._profile_from_policy(agent_policy)),
        ):
            model = self._model_from_profile(profile)
            if model is not None:
                return model, source_name
        return None, "unresolved"

    def _resolve_max_steps(
        self,
        task_profile: DispatchProfile | None,
        project_profile: DispatchProfile | None,
        system_profile: DispatchProfile | None,
        agent_policy: AgentRoutingPolicy | None,
    ) -> tuple[int | None, str]:
        for source_name, profile in (
            ("task_override", task_profile),
            ("project_default", project_profile),
            ("system_default", system_profile),
            ("agent_fallback", self._profile_from_policy(agent_policy)),
        ):
            max_steps = self._max_steps_from_profile(profile)
            if max_steps is not None:
                return max_steps, source_name
        return None, "unresolved"

    def _resolve_model_profile_name(
        self,
        task_profile: DispatchProfile | None,
        project_profile: DispatchProfile | None,
        system_profile: DispatchProfile | None,
        agent_policy: AgentRoutingPolicy | None,
    ) -> str | None:
        for profile in (
            task_profile,
            project_profile,
            system_profile,
            self._profile_from_policy(agent_policy),
        ):
            if profile is not None and profile.model_profile is not None:
                return profile.model_profile.profile_name
        return None

    @staticmethod
    def _provider_name_from_profile(profile: DispatchProfile | None) -> str | None:
        if profile is None:
            return None
        if profile.provider is not None and profile.provider.provider_name:
            return profile.provider.provider_name
        if profile.model_profile is not None and profile.model_profile.provider_name:
            return profile.model_profile.provider_name
        return None

    @staticmethod
    def _model_from_profile(profile: DispatchProfile | None) -> str | None:
        if profile is None:
            return None
        if profile.provider is not None and profile.provider.model:
            return profile.provider.model
        if profile.model_profile is not None and profile.model_profile.model:
            return profile.model_profile.model
        return None

    @staticmethod
    def _max_steps_from_profile(profile: DispatchProfile | None) -> int | None:
        if profile is None:
            return None
        if profile.max_steps is not None:
            return profile.max_steps
        if profile.model_profile is not None and profile.model_profile.max_steps is not None:
            return profile.model_profile.max_steps
        return None
