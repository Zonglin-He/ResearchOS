from __future__ import annotations

from dataclasses import dataclass

from app.routing.models import DispatchProfile, ModelProfile, ProviderSpec


@dataclass(frozen=True)
class ProviderModelChoice:
    label: str
    provider_name: str
    model: str


@dataclass(frozen=True)
class DispatchProfileChoice:
    label: str
    dispatch_profile: DispatchProfile | None
    description: str = ""


KNOWN_PROVIDER_MODELS: dict[str, list[ProviderModelChoice]] = {
    "claude": [
        ProviderModelChoice("Claude Sonnet", "claude", "sonnet"),
        ProviderModelChoice("Claude Haiku", "claude", "haiku"),
    ],
    "codex": [
        ProviderModelChoice("Codex GPT-5.4", "codex", "gpt-5.4"),
        ProviderModelChoice("Codex GPT-5.4 Mini", "codex", "gpt-5.4-mini"),
    ],
    "gemini": [
        ProviderModelChoice("Gemini 3.1 Pro Preview", "gemini", "gemini-3.1-pro-preview"),
        ProviderModelChoice("Gemini 3 Flash Preview", "gemini", "gemini-3-flash-preview"),
        ProviderModelChoice(
            "Gemini 3.1 Flash-Lite Preview",
            "gemini",
            "gemini-3.1-flash-lite-preview",
        ),
    ],
    "local": [
        ProviderModelChoice("Local Default", "local", "default"),
    ],
}


def available_model_choices(provider_name: str) -> list[ProviderModelChoice]:
    return list(KNOWN_PROVIDER_MODELS.get(provider_name, []))


def build_dispatch_profile(
    provider_name: str,
    model: str,
    *,
    max_steps: int | None = None,
    profile_name: str | None = None,
) -> DispatchProfile:
    normalized_name = provider_name.lower()
    resolved_profile_name = profile_name or f"{normalized_name}-{model}"
    return DispatchProfile(
        provider=ProviderSpec(provider_name=normalized_name, model=model),
        model_profile=ModelProfile(
            profile_name=resolved_profile_name,
            provider_name=normalized_name,
            model=model,
            max_steps=max_steps,
        ),
        max_steps=max_steps,
        metadata={"selection": "interactive"},
    )


def available_dispatch_profile_choices(system_default: DispatchProfile) -> list[DispatchProfileChoice]:
    choices = [
        DispatchProfileChoice(
            label="Inherit system default",
            dispatch_profile=None,
            description=(
                f"{system_default.provider.provider_name if system_default.provider else 'default'} / "
                f"{system_default.provider.model if system_default.provider and system_default.provider.model else '<default>'}"
            ),
        )
    ]
    for provider_name, model_choices in KNOWN_PROVIDER_MODELS.items():
        for choice in model_choices:
            if choice.model == "default":
                profile = build_dispatch_profile(provider_name, choice.model)
            else:
                profile = build_dispatch_profile(provider_name, choice.model)
            choices.append(
                DispatchProfileChoice(
                    label=choice.label,
                    dispatch_profile=profile,
                    description=f"{provider_name} / {choice.model}",
                )
            )
    return choices
