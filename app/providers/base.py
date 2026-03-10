from abc import abstractmethod, ABC
from typing import Any


class BaseProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_input: str,
        tools: list[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        ...