from dataclasses import dataclass
from typing import Any


@dataclass
class Message:
    sender: str
    receiver: str
    type: str
    payload: dict[str, Any]
    correlation_id: str
