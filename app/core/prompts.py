from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_prompt_path(path: str | Path) -> Path:
    prompt_path = Path(path)
    if prompt_path.is_absolute():
        return prompt_path
    return (repo_root() / prompt_path).resolve()
