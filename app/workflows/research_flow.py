from dataclasses import dataclass

from app.core.enums import Stage


@dataclass
class ResearchFlow:
    stage: Stage = Stage.NEW_TOPIC

    def advance(self, next_stage: Stage) -> Stage:
        self.stage = next_stage
        return self.stage
