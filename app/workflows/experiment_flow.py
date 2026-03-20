from dataclasses import dataclass, field


@dataclass
class ExperimentFlow:
    run_ids: list[str] = field(default_factory=list)

    def register_run(self, run_id: str) -> None:
        self.run_ids.append(run_id)
