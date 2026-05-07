import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    topic: str
    payload: Any
    timestamp: float = field(default_factory=time.time)
