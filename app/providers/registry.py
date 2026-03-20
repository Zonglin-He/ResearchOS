from __future__ import annotations

from collections.abc import Callable

from app.providers.base import BaseProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], BaseProvider]] = {}
        self._instances: dict[str, BaseProvider] = {}

    def register(self, provider_name: str, factory: Callable[[], BaseProvider]) -> None:
        self._factories[provider_name] = factory

    def get(self, provider_name: str) -> BaseProvider:
        if provider_name not in self._instances:
            factory = self._factories.get(provider_name)
            if factory is None:
                raise KeyError(f"Provider not registered: {provider_name}")
            self._instances[provider_name] = factory()
        return self._instances[provider_name]

    def list_names(self) -> list[str]:
        return sorted(self._factories)
