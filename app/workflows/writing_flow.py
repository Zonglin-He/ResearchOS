from dataclasses import dataclass, field


@dataclass
class WritingFlow:
    sections: list[str] = field(default_factory=list)

    def add_section(self, section_name: str) -> None:
        self.sections.append(section_name)
