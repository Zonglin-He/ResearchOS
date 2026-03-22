from dataclasses import dataclass, field
import os

from app.core.constants import (
    DEFAULT_DATABASE_URL,
    DEFAULT_DB_PATH,
    DEFAULT_MAX_STEPS,
    DEFAULT_PROVIDER,
    DEFAULT_REDIS_URL,
)


@dataclass
class AppConfig:
    db_path: str = DEFAULT_DB_PATH
    database_url: str = DEFAULT_DATABASE_URL
    redis_url: str = DEFAULT_REDIS_URL
    celery_backend: str = DEFAULT_REDIS_URL
    max_steps: int = DEFAULT_MAX_STEPS
    provider_name: str = DEFAULT_PROVIDER
    provider_model: str = ""
    workspace_root: str = os.getcwd()
    provider_explicit: bool = False
    provider_model_explicit: bool = False
    disabled_provider_families: tuple[str, ...] = ()
    provider_cooldown_seconds: int = 300
    human_checkpoints: dict[str, str] = field(
        default_factory=lambda: {
            "MAP_GAPS": "optional",
            "HUMAN_SELECT": "required",
            "FREEZE_SPEC": "optional",
            "AUDIT_RESULTS": "optional",
            "WRITE_DRAFT": "optional",
        }
    )


def load_config() -> AppConfig:
    provider_env = os.getenv("RESEARCHOS_PROVIDER")
    provider_model_env = os.getenv("RESEARCHOS_PROVIDER_MODEL")
    disabled_env = os.getenv("RESEARCHOS_DISABLED_PROVIDER_FAMILIES", "")
    return AppConfig(
        db_path=os.getenv("RESEARCHOS_DB_PATH", DEFAULT_DB_PATH),
        database_url=os.getenv("RESEARCHOS_DATABASE_URL", DEFAULT_DATABASE_URL),
        redis_url=os.getenv("RESEARCHOS_REDIS_URL", DEFAULT_REDIS_URL),
        celery_backend=os.getenv("RESEARCHOS_CELERY_BACKEND", DEFAULT_REDIS_URL),
        max_steps=int(os.getenv("RESEARCHOS_MAX_STEPS", DEFAULT_MAX_STEPS)),
        provider_name=provider_env or DEFAULT_PROVIDER,
        provider_model=provider_model_env or "",
        workspace_root=os.getenv("RESEARCHOS_WORKSPACE_ROOT", os.getcwd()),
        provider_explicit=provider_env is not None,
        provider_model_explicit=provider_model_env is not None,
        disabled_provider_families=tuple(
            item.strip().lower() for item in disabled_env.split(",") if item.strip()
        ),
        provider_cooldown_seconds=int(
            os.getenv("RESEARCHOS_PROVIDER_COOLDOWN_SECONDS", "300")
        ),
    )
