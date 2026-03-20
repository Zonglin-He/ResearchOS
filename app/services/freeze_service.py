from __future__ import annotations

from pathlib import Path

from app.schemas.freeze import ResultsFreeze, SpecFreeze, TopicFreeze
from app.services.registry_store import read_yaml, to_record, write_yaml


class FreezeService:
    def __init__(self, freeze_dir: str | Path = "registry/freezes") -> None:
        self.freeze_dir = Path(freeze_dir)

    def save_topic_freeze(self, freeze: TopicFreeze) -> TopicFreeze:
        write_yaml(self.freeze_dir / "topic_freeze.yaml", to_record(freeze))
        return freeze

    def load_topic_freeze(self) -> TopicFreeze | None:
        data = read_yaml(self.freeze_dir / "topic_freeze.yaml")
        if data is None:
            return None
        return TopicFreeze(**data)

    def save_spec_freeze(self, freeze: SpecFreeze) -> SpecFreeze:
        write_yaml(self.freeze_dir / "spec_freeze.yaml", to_record(freeze))
        return freeze

    def load_spec_freeze(self) -> SpecFreeze | None:
        data = read_yaml(self.freeze_dir / "spec_freeze.yaml")
        if data is None:
            return None
        return SpecFreeze(**data)

    def save_results_freeze(self, freeze: ResultsFreeze) -> ResultsFreeze:
        write_yaml(self.freeze_dir / "results_freeze.yaml", to_record(freeze))
        return freeze

    def load_results_freeze(self) -> ResultsFreeze | None:
        data = read_yaml(self.freeze_dir / "results_freeze.yaml")
        if data is None:
            return None
        return ResultsFreeze(**data)
