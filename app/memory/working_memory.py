from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkingMemory:
    run_id: str
    task_id: str
    entries: dict[str, Any] = field(default_factory=dict)

    def put(self, key: str, value: Any) -> None:
        self.entries[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.entries.get(key, default)
