from __future__ import annotations

from app.routing.models import (
    AgentRoutingPolicy,
    DispatchProfile,
    ResolvedDispatch,
    RoleRoutingPolicy,
    RoutingDecisionReason,
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
        role_policy = agent_policy.resolve_role_policy(task.kind) if agent_policy is not None else None

        provider_name, provider_source = self._resolve_provider_name(
            task_profile,
            project_profile,
            system_profile,
            role_policy,
            agent_policy,
        )
        if provider_name is None:
            raise ValueError(
                f"Unable to resolve provider for task {task.task_id} and agent "
                f"{agent_policy.agent_name if agent_policy else '<unknown>'}"
            )

        model, model_source = self._resolve_model(
            provider_name=provider_name,
            task_profile=task_profile,
            project_profile=project_profile,
            system_profile=system_profile,
            role_policy=role_policy,
            agent_policy=agent_policy,
        )
        max_steps, max_steps_source = self._resolve_max_steps(
            task_profile,
            project_profile,
            system_profile,
            role_policy,
            agent_policy,
        )
        model_profile_name = self._resolve_model_profile_name(
            task_profile,
            project_profile,
            system_profile,
            agent_policy,
        )
        fallback_chain = self._build_fallback_chain(
            provider_name=provider_name,
            role_policy=role_policy,
            agent_policy=agent_policy,
        )
        candidate_models = self._build_candidate_models(
            provider_name=provider_name,
            task_profile=task_profile,
            project_profile=project_profile,
            system_profile=system_profile,
            role_policy=role_policy,
            agent_policy=agent_policy,
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
        if role_policy is not None:
            metadata["max_attempts_per_invocation"] = (
                role_policy.invocation_budget_policy.max_attempts_per_invocation
            )
            metadata["prefer_low_cost"] = role_policy.invocation_budget_policy.prefer_low_cost
            metadata["allow_expensive_upgrade"] = (
                role_policy.invocation_budget_policy.allow_expensive_upgrade
            )

        return ResolvedDispatch(
            provider_name=provider_name,
            provider_family=provider_name,
            model=model,
            model_profile_name=model_profile_name,
            max_steps=max_steps,
            role_name=role_policy.role_name if role_policy is not None else None,
            capability_class=role_policy.capability_class if role_policy is not None else None,
            candidate_models=candidate_models,
            fallback_chain=fallback_chain,
            decision_reason=self._decision_reason_for_source(provider_source),
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
        role_policy: RoleRoutingPolicy | None,
        agent_policy: AgentRoutingPolicy | None,
    ) -> tuple[str | None, str]:
        if (provider_name := self._provider_name_from_profile(task_profile)) is not None:
            return provider_name, "task_override"
        if (provider_name := self._provider_name_from_profile(project_profile)) is not None:
            return provider_name, "project_default"
        if self._system_profile_is_explicit(system_profile):
            provider_name = self._provider_name_from_profile(system_profile)
            if provider_name is not None:
                return provider_name, "system_default"
        if role_policy is not None and role_policy.family_priority:
            return role_policy.family_priority[0], "role_default"
        if (provider_name := self._provider_name_from_profile(system_profile)) is not None:
            return provider_name, "system_default"
        provider_name = self._provider_name_from_profile(self._profile_from_policy(agent_policy))
        if provider_name is not None:
            return provider_name, "agent_fallback"
        return None, "unresolved"

    def _resolve_model(
        self,
        *,
        provider_name: str,
        task_profile: DispatchProfile | None,
        project_profile: DispatchProfile | None,
        system_profile: DispatchProfile | None,
        role_policy: RoleRoutingPolicy | None,
        agent_policy: AgentRoutingPolicy | None,
    ) -> tuple[str | None, str]:
        if (model := self._model_from_profile(task_profile)) is not None:
            return model, "task_override"
        if (model := self._model_from_profile(project_profile)) is not None:
            return model, "project_default"
        if self._system_profile_is_explicit(system_profile):
            model = self._model_from_profile(system_profile)
            if model is not None:
                return model, "system_default"
        if role_policy is not None:
            family_models = role_policy.family_model_priority.get(provider_name, [])
            if family_models:
                return family_models[0], "role_default"
        if (model := self._model_from_profile(system_profile)) is not None:
            return model, "system_default"
        model = self._model_from_profile(self._profile_from_policy(agent_policy))
        if model is not None:
            return model, "agent_fallback"
        return None, "unresolved"

    def _resolve_max_steps(
        self,
        task_profile: DispatchProfile | None,
        project_profile: DispatchProfile | None,
        system_profile: DispatchProfile | None,
        role_policy: RoleRoutingPolicy | None,
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
        if role_policy is not None:
            return role_policy.invocation_budget_policy.max_attempts_per_invocation * 3, "role_default"
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

    def _build_fallback_chain(
        self,
        *,
        provider_name: str,
        role_policy: RoleRoutingPolicy | None,
        agent_policy: AgentRoutingPolicy | None,
    ) -> list[str]:
        chain: list[str] = [provider_name]
        role_chain = role_policy.fallback_chain.families if role_policy is not None else []
        for family in role_chain:
            if family not in chain:
                chain.append(family)
        agent_fallback = self._provider_name_from_profile(self._profile_from_policy(agent_policy))
        if agent_fallback is not None and agent_fallback not in chain:
            chain.append(agent_fallback)
        return chain

    def _build_candidate_models(
        self,
        *,
        provider_name: str,
        task_profile: DispatchProfile | None,
        project_profile: DispatchProfile | None,
        system_profile: DispatchProfile | None,
        role_policy: RoleRoutingPolicy | None,
        agent_policy: AgentRoutingPolicy | None,
    ) -> dict[str, list[str]]:
        models: dict[str, list[str]] = {}
        for family in self._build_fallback_chain(
            provider_name=provider_name,
            role_policy=role_policy,
            agent_policy=agent_policy,
        ):
            family_models: list[str] = []
            if family == provider_name:
                explicit = self._first_non_none(
                    self._model_from_profile(task_profile),
                    self._model_from_profile(project_profile),
                    self._model_from_profile(system_profile)
                    if self._system_profile_is_explicit(system_profile)
                    else None,
                )
                if explicit is not None:
                    family_models.append(explicit)
            if role_policy is not None:
                family_models.extend(role_policy.family_model_priority.get(family, []))
            if family == self._provider_name_from_profile(self._profile_from_policy(agent_policy)):
                fallback_model = self._model_from_profile(self._profile_from_policy(agent_policy))
                if fallback_model is not None:
                    family_models.append(fallback_model)
            if family == self._provider_name_from_profile(system_profile):
                system_model = self._model_from_profile(system_profile)
                if system_model is not None:
                    family_models.append(system_model)
            models[family] = self._dedupe_preserve_order(family_models)
        return models

    @staticmethod
    def _decision_reason_for_source(source: str) -> str | None:
        mapping = {
            "task_override": RoutingDecisionReason.TASK_OVERRIDE.value,
            "project_default": RoutingDecisionReason.PROJECT_DEFAULT.value,
            "system_default": RoutingDecisionReason.SYSTEM_DEFAULT.value,
            "role_default": RoutingDecisionReason.ROLE_DEFAULT.value,
            "agent_fallback": RoutingDecisionReason.AGENT_FALLBACK.value,
        }
        return mapping.get(source)

    @staticmethod
    def _system_profile_is_explicit(profile: DispatchProfile | None) -> bool:
        if profile is None:
            return False
        return profile.metadata.get("source") == "env_explicit"

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

    @staticmethod
    def _first_non_none(*values):
        for value in values:
            if value is not None:
                return value
        return None

    @staticmethod
    def _dedupe_preserve_order(values: list[str]) -> list[str]:
        ordered: list[str] = []
        for value in values:
            if value and value not in ordered:
                ordered.append(value)
        return ordered
