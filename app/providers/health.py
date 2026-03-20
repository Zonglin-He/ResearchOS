from __future__ import annotations

from datetime import datetime, timedelta, timezone
import shutil

from app.providers.command_provider import CommandProvider
from app.providers.local_provider import LocalProvider
from app.providers.registry import ProviderRegistry
from app.routing.models import (
    ProviderAvailabilityState,
    ProviderFailureClass,
    ProviderFamily,
    ProviderHealthSnapshot,
)


class ProviderHealthService:
    RATE_LIMIT_SIGNATURES = ("rate limit", "too many requests", "429")
    EXHAUSTION_SIGNATURES = (
        "quota",
        "usage limit",
        "usage cap",
        "credit balance",
        "exhausted",
        "billing hard limit",
    )
    AUTH_SIGNATURES = (
        "auth",
        "login",
        "unauthorized",
        "forbidden",
        "api key",
        "credential",
        "not logged in",
    )
    PROCESS_SIGNATURES = (
        "not found",
        "not recognized",
        "no such file",
        "provider failed",
        "command failed",
    )

    def __init__(
        self,
        *,
        cooldown_seconds: int = 300,
        disabled_families: set[str] | None = None,
    ) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.disabled_families = {family.lower() for family in disabled_families or set()}
        self._cooldowns: dict[str, datetime] = {}
        self._last_failure_class: dict[str, ProviderFailureClass] = {}
        self._last_failure_detail: dict[str, str] = {}

    def snapshot(self, provider_name: str, registry: ProviderRegistry) -> ProviderHealthSnapshot:
        family = provider_name.lower()
        if family in self.disabled_families:
            return ProviderHealthSnapshot(
                provider_family=family,
                state=ProviderAvailabilityState.DISABLED.value,
                cli_installed=self._is_cli_installed(family, registry),
                manually_disabled=True,
                detail="Provider family manually disabled by operator configuration.",
            )

        installed = self._is_cli_installed(family, registry)
        if not installed:
            return ProviderHealthSnapshot(
                provider_family=family,
                state=ProviderAvailabilityState.UNHEALTHY.value,
                cli_installed=False,
                failure_class=ProviderFailureClass.PROCESS_FAILURE.value,
                detail="Provider CLI is not installed or not discoverable on PATH.",
            )

        cooldown_until = self._cooldowns.get(family)
        if cooldown_until is not None and cooldown_until > self._now():
            remaining = int((cooldown_until - self._now()).total_seconds())
            failure_class = self._last_failure_class.get(family)
            state = ProviderAvailabilityState.DEGRADED
            if failure_class == ProviderFailureClass.RATE_LIMIT:
                state = ProviderAvailabilityState.RATE_LIMITED
            elif failure_class == ProviderFailureClass.QUOTA_EXHAUSTION:
                state = ProviderAvailabilityState.EXHAUSTED
            elif failure_class in {ProviderFailureClass.AUTH_CONFIG, ProviderFailureClass.PROCESS_FAILURE}:
                state = ProviderAvailabilityState.UNHEALTHY
            return ProviderHealthSnapshot(
                provider_family=family,
                state=state.value,
                cli_installed=True,
                failure_class=failure_class.value if failure_class is not None else None,
                detail=self._last_failure_detail.get(family, ""),
                cooldown_seconds_remaining=max(0, remaining),
            )

        return ProviderHealthSnapshot(
            provider_family=family,
            state=ProviderAvailabilityState.AVAILABLE.value,
            cli_installed=True,
        )

    def record_success(self, provider_name: str) -> ProviderHealthSnapshot:
        family = provider_name.lower()
        self._cooldowns.pop(family, None)
        self._last_failure_class.pop(family, None)
        self._last_failure_detail.pop(family, None)
        return ProviderHealthSnapshot(
            provider_family=family,
            state=ProviderAvailabilityState.AVAILABLE.value,
            cli_installed=True,
        )

    def record_failure(
        self,
        provider_name: str,
        error: Exception,
        registry: ProviderRegistry,
    ) -> ProviderHealthSnapshot:
        family = provider_name.lower()
        snapshot = self.classify_failure(provider_name, error, registry)
        failure_class = snapshot.failure_class
        if failure_class is not None:
            self._last_failure_class[family] = ProviderFailureClass(failure_class)
        self._last_failure_detail[family] = snapshot.detail
        if snapshot.state in {
            ProviderAvailabilityState.RATE_LIMITED.value,
            ProviderAvailabilityState.EXHAUSTED.value,
            ProviderAvailabilityState.DEGRADED.value,
        }:
            self._cooldowns[family] = self._now() + timedelta(seconds=self.cooldown_seconds)
            return self.snapshot(provider_name, registry)
        if snapshot.state == ProviderAvailabilityState.UNHEALTHY.value:
            self._cooldowns[family] = self._now() + timedelta(seconds=self.cooldown_seconds)
            return self.snapshot(provider_name, registry)
        return snapshot

    def classify_failure(
        self,
        provider_name: str,
        error: Exception,
        registry: ProviderRegistry,
    ) -> ProviderHealthSnapshot:
        family = provider_name.lower()
        message = str(error).lower()
        installed = self._is_cli_installed(family, registry)

        if any(signature in message for signature in self.RATE_LIMIT_SIGNATURES):
            return ProviderHealthSnapshot(
                provider_family=family,
                state=ProviderAvailabilityState.RATE_LIMITED.value,
                cli_installed=installed,
                failure_class=ProviderFailureClass.RATE_LIMIT.value,
                detail=str(error),
            )
        if any(signature in message for signature in self.EXHAUSTION_SIGNATURES):
            return ProviderHealthSnapshot(
                provider_family=family,
                state=ProviderAvailabilityState.EXHAUSTED.value,
                cli_installed=installed,
                failure_class=ProviderFailureClass.QUOTA_EXHAUSTION.value,
                detail=str(error),
            )
        if any(signature in message for signature in self.AUTH_SIGNATURES):
            return ProviderHealthSnapshot(
                provider_family=family,
                state=ProviderAvailabilityState.UNHEALTHY.value,
                cli_installed=installed,
                failure_class=ProviderFailureClass.AUTH_CONFIG.value,
                detail=str(error),
            )
        if not installed or any(signature in message for signature in self.PROCESS_SIGNATURES):
            return ProviderHealthSnapshot(
                provider_family=family,
                state=ProviderAvailabilityState.UNHEALTHY.value,
                cli_installed=installed,
                failure_class=ProviderFailureClass.PROCESS_FAILURE.value,
                detail=str(error),
            )
        return ProviderHealthSnapshot(
            provider_family=family,
            state=ProviderAvailabilityState.DEGRADED.value,
            cli_installed=installed,
            failure_class=ProviderFailureClass.UNKNOWN_TRANSIENT.value,
            detail=str(error),
        )

    def disable_family(self, provider_name: str) -> None:
        self.disabled_families.add(provider_name.lower())

    def enable_family(self, provider_name: str) -> None:
        self.disabled_families.discard(provider_name.lower())

    def _is_cli_installed(self, provider_name: str, registry: ProviderRegistry) -> bool:
        provider = registry.get(provider_name)
        if isinstance(provider, LocalProvider):
            return True
        if isinstance(provider, CommandProvider):
            return shutil.which(provider.command_name) is not None
        return True

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
