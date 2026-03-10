from abc import ABC, abstractmethod

from app.schemas.context import RunContext
from app.schemas.result import AgentResult
from app.schemas.task import Task


class BaseAgent(ABC):
    name: str
    description: str

    @abstractmethod
    async def run(self, task: Task, ctx: RunContext) -> AgentResult:
        ...

