from pathlib import Path

from app.providers.health import ProviderHealthService
from app.providers.registry import ProviderRegistry


def test_provider_health_state_persists_disabled_families_and_cooldowns(tmp_path: Path) -> None:
    state_path = tmp_path / "state" / "provider_health.yaml"
    registry = ProviderRegistry()
    registry.register("claude", lambda: object())
    registry.register("gemini", lambda: object())

    service = ProviderHealthService(state_path=state_path, cooldown_seconds=300)
    service.disable_family("claude")
    service.record_failure("gemini", RuntimeError("rate limit"), registry)

    reloaded = ProviderHealthService(state_path=state_path, cooldown_seconds=300)
    claude_snapshot = reloaded.snapshot("claude", registry)
    gemini_snapshot = reloaded.snapshot("gemini", registry)

    assert claude_snapshot.state == "disabled"
    assert gemini_snapshot.state == "rate_limited"
    assert gemini_snapshot.cooldown_seconds_remaining > 0
