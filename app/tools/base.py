from abc import abstractmethod, ABC


class BaseTool(ABC):
    name: str
    description: str
    input_schema: dict

    @abstractmethod
    async def execute(self, **kwargs) -> dict:
        ...
