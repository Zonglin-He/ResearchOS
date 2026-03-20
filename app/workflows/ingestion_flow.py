from dataclasses import dataclass, field


@dataclass
class IngestionFlow:
    sources: list[str] = field(default_factory=list)

    def add_source(self, source: str) -> None:
        self.sources.append(source)
