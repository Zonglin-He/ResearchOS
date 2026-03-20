from dataclasses import dataclass
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


def load_config() -> AppConfig:
    return AppConfig(
        db_path=os.getenv("RESEARCHOS_DB_PATH", DEFAULT_DB_PATH),
        database_url=os.getenv("RESEARCHOS_DATABASE_URL", DEFAULT_DATABASE_URL),
        redis_url=os.getenv("RESEARCHOS_REDIS_URL", DEFAULT_REDIS_URL),
        celery_backend=os.getenv("RESEARCHOS_CELERY_BACKEND", DEFAULT_REDIS_URL),
        max_steps=int(os.getenv("RESEARCHOS_MAX_STEPS", DEFAULT_MAX_STEPS)),
        provider_name=os.getenv("RESEARCHOS_PROVIDER", DEFAULT_PROVIDER),
        provider_model=os.getenv("RESEARCHOS_PROVIDER_MODEL", ""),
        workspace_root=os.getenv("RESEARCHOS_WORKSPACE_ROOT", os.getcwd()),
    )
