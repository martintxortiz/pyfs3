import logging
import time
from typing import Any

from .message import Message
from .software_bus import SoftwareBus

logger = logging.getLogger(__name__)


class EventServices:
    """Publishes rate-limited event messages."""

    def __init__(self, bus: SoftwareBus):
        self.bus = bus
        self._last_sent: dict[str, float] = {}

    def emit(
        self,
        topic: str,
        payload: Any,
        min_interval_seconds: float = 0.0,
        key: str | None = None,
    ) -> bool:
        event_key = key or f"{topic}:{payload}"
        now = time.monotonic()
        last_sent = self._last_sent.get(event_key)

        rate_limited = (
            min_interval_seconds > 0
            and last_sent is not None
            and now - last_sent < min_interval_seconds
        )
        if rate_limited:
            logger.debug("Event rate limited: %s", event_key)
            return False

        self.bus.publish(Message(topic=topic, payload=payload))
        self._last_sent[event_key] = now
        return True
