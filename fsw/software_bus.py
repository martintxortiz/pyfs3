import logging
import queue
import threading

from .message import Message

logger = logging.getLogger(__name__)


class SoftwareBus:
    """Thread-safe, non-blocking publish/subscribe message bus."""

    def __init__(self, maxsize: int = 100):
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[queue.Queue[Message]]] = {}
        self._maxsize = maxsize

    def subscribe(self, topic: str) -> queue.Queue[Message]:
        """Register interest in a topic and return a dedicated queue."""
        inbox: queue.Queue[Message] = queue.Queue(maxsize=self._maxsize)
        with self._lock:
            self._subscribers.setdefault(topic, []).append(inbox)
        logger.debug("New subscriber on topic '%s'", topic)
        return inbox

    def unsubscribe(self, topic: str, inbox: queue.Queue[Message]) -> None:
        """Remove one subscriber queue from a topic."""
        with self._lock:
            subscribers = self._subscribers.get(topic, [])
            if inbox in subscribers:
                subscribers.remove(inbox)
            if not subscribers and topic in self._subscribers:
                del self._subscribers[topic]

    def publish(self, msg: Message) -> None:
        """Publish a message without blocking the calling thread."""
        with self._lock:
            subscribers = list(self._subscribers.get(msg.topic, []))

        for inbox in subscribers:
            try:
                inbox.put_nowait(msg)
            except queue.Full:
                logger.warning("Queue full on topic '%s'; message dropped", msg.topic)
