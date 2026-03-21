from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.providers.health import ProviderHealthService
from app.providers.registry import ProviderRegistry
from app.routing.models import (
    ProviderAvailabilityState,
    ProviderFamily,
    ResolvedDispatch,
    RoutingDecisionReason,
)


class ProviderInvocationService:
    def __init__(
        self,
        provider_registry: ProviderRegistry,
        health_service: ProviderHealthService,
    ) -> None:
        self.provider_registry = provider_registry
        self.health_service = health_service

    async def generate(
        self,
        *,
        routing: ResolvedDispatch,
        system_prompt: str,
        user_input: str,
        tools: list[dict[str, Any]] | None,
        response_schema: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], ResolvedDispatch]:
        attempted_snapshots = []
        preferred_provider = routing.provider_name
        families = routing.fallback_chain or [preferred_provider]
        last_error: Exception | None = None

        max_attempts = routing.metadata.get("max_attempts_per_invocation")
        attempts_remaining = int(max_attempts) if max_attempts is not None else len(families)

        for family in families:
            if attempts_remaining <= 0:
                break
            attempts_remaining -= 1

            snapshot = self.health_service.snapshot(family, self.provider_registry)
            attempted_snapshots.append(snapshot)
            if snapshot.state in {
                ProviderAvailabilityState.DISABLED.value,
                ProviderAvailabilityState.RATE_LIMITED.value,
                ProviderAvailabilityState.EXHAUSTED.value,
                ProviderAvailabilityState.UNHEALTHY.value,
            }:
                continue

            provider = self.provider_registry.get(family)
            candidate_models = routing.candidate_models.get(family) or [routing.model]
            if not candidate_models:
                candidate_models = [None]

            for model in candidate_models:
                try:
                    output = await provider.generate(
                        system_prompt=system_prompt,
                        user_input=user_input,
                        tools=tools,
                        response_schema=response_schema,
                        model=model,
                    )
                    success_snapshot = self.health_service.record_success(family)
                    attempted_snapshots[-1] = success_snapshot
                    final_routing = deepcopy(routing)
                    final_routing.provider_name = family
                    final_routing.provider_family = family
                    final_routing.model = model
                    final_routing.health_snapshots = attempted_snapshots.copy()
                    final_routing.fallback_reason = self._fallback_reason(
                        preferred_provider=preferred_provider,
                        chosen_provider=family,
                        attempted_snapshots=attempted_snapshots,
                    )
                    return output, final_routing
                except Exception as error:
                    last_error = error
                    attempted_snapshots[-1] = self.health_service.record_failure(
                        family,
                        error,
                        self.provider_registry,
                    )
                    if attempted_snapshots[-1].failure_class in {
                        "auth_config",
                        "process_failure",
                        "rate_limit",
                        "quota_exhaustion",
                    }:
                        break

        final_routing = deepcopy(routing)
        final_routing.health_snapshots = attempted_snapshots
        if preferred_provider == ProviderFamily.LOCAL.value:
            final_routing.fallback_reason = RoutingDecisionReason.LOCAL_DETERMINISTIC_FALLBACK.value
        if last_error is None:
            raise RuntimeError(
                "No provider family was available for invocation based on current routing and health state."
            )
        detail = str(last_error).strip()
        if not detail:
            detail = "; ".join(
                f"{snapshot.provider_family}: {snapshot.detail or snapshot.state}"
                for snapshot in attempted_snapshots
            )
        raise RuntimeError(f"All provider families failed for routing plan: {detail}") from last_error

    @staticmethod
    def _fallback_reason(
        *,
        preferred_provider: str,
        chosen_provider: str,
        attempted_snapshots: list,
    ) -> str | None:
        if chosen_provider == preferred_provider:
            return None
        for snapshot in attempted_snapshots:
            if snapshot.provider_family != preferred_provider:
                continue
            if snapshot.state == ProviderAvailabilityState.RATE_LIMITED.value:
                return RoutingDecisionReason.RATE_LIMIT_FALLBACK.value
            if snapshot.state == ProviderAvailabilityState.EXHAUSTED.value:
                return RoutingDecisionReason.EXHAUSTION_FALLBACK.value
            if snapshot.state in {
                ProviderAvailabilityState.UNHEALTHY.value,
                ProviderAvailabilityState.DEGRADED.value,
                ProviderAvailabilityState.DISABLED.value,
            }:
                return RoutingDecisionReason.HEALTH_FALLBACK.value
        return RoutingDecisionReason.HEALTH_FALLBACK.value
