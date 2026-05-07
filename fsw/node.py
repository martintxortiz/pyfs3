import logging
import queue
import threading
from abc import ABC, abstractmethod
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from typing import Any, TypeVar

from .event_services import EventServices
from .message import Message
from .software_bus import SoftwareBus

logger = logging.getLogger(__name__)
T = TypeVar("T")


class NodeState(Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class Node(ABC):
    """Base class for flight software applications."""

    def __init__(
        self,
        name: str,
        bus: SoftwareBus,
        config: dict | None = None,
        events: EventServices | None = None,
    ):
        self.name = name
        self.bus = bus
        self.events = events
        self.log = logging.getLogger(self.name)
        self.config = config or {}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._subscriptions: list[tuple[str, queue.Queue[Message]]] = []
        self._started = False
        self.state = NodeState.CREATED
        self.last_error: str | None = None

    # Lifecycle hooks for app subclasses.

    def init(self) -> None:
        pass

    @abstractmethod
    def run(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def load_config(self, config_type: type[T]) -> T:
        """Load app config into a small typed dataclass."""
        if not is_dataclass(config_type):
            raise TypeError("config_type must be a dataclass")

        values = {}
        known_keys = {field.name for field in fields(config_type)}

        for key in sorted(set(self.config) - known_keys):
            self.log.warning("Unused config key ignored: %s", key)

        for field in fields(config_type):
            if field.name in self.config:
                value = self.config[field.name]
            elif field.default is not MISSING:
                value = field.default
            elif field.default_factory is not MISSING:
                value = field.default_factory()
            else:
                raise ValueError(f"Missing required config key: {field.name}")

            values[field.name] = _check_type(field.name, value, field.type)

        return config_type(**values)

    def emit_event(
        self,
        topic: str,
        payload: Any,
        min_interval_seconds: float = 0.0,
    ) -> bool:
        key = f"{self.name}:{topic}:{payload}"
        if self.events:
            return self.events.emit(topic, payload, min_interval_seconds, key=key)

        self.bus.publish(Message(topic=topic, payload=payload))
        return True

    def subscribe(self, topic: str) -> queue.Queue[Message]:
        inbox = self.bus.subscribe(topic)
        self._subscriptions.append((topic, inbox))
        return inbox

    def get_message(
        self,
        inbox: queue.Queue[Message],
        timeout: float,
    ) -> Message | None:
        try:
            return inbox.get(timeout=timeout)
        except queue.Empty:
            return None

    # Internal interface used by ExecutiveServices.

    def _start(self) -> bool:
        if self._thread and self._thread.is_alive():
            logger.info("[%s] already running", self.name)
            return True

        self._stop_event.clear()
        self.last_error = None
        try:
            self.init()
        except Exception as error:
            self.state = NodeState.FAILED
            self.last_error = str(error)
            logger.exception("[%s] failed to initialize", self.name)
            return False

        self._started = True
        self.state = NodeState.RUNNING
        self._thread = threading.Thread(
            target=self._run_wrapper,
            name=self.name,
            daemon=True,
        )
        self._thread.start()
        logger.info("[%s] started", self.name)
        return True

    def _stop(self) -> bool:
        if not self._started:
            return True

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)

        try:
            self.shutdown()
            self._unsubscribe_all()
        except Exception as error:
            self.state = NodeState.FAILED
            self.last_error = str(error)
            logger.exception("[%s] failed during shutdown", self.name)
            return False

        self._thread = None
        self._started = False
        if self.state is not NodeState.FAILED:
            self.state = NodeState.STOPPED
        logger.info("[%s] stopped", self.name)
        return True

    def _run_wrapper(self) -> None:
        try:
            self.run()
        except Exception as error:
            self.state = NodeState.FAILED
            self.last_error = str(error)
            logger.exception("[%s] crashed", self.name)

    def _unsubscribe_all(self) -> None:
        for topic, inbox in self._subscriptions:
            self.bus.unsubscribe(topic, inbox)
        self._subscriptions = []


def _check_type(name: str, value, expected_type):
    if expected_type is float and isinstance(value, int) and not isinstance(value, bool):
        return float(value)

    if expected_type in (str, int, float, bool) and not isinstance(value, expected_type):
        raise ValueError(
            f"Config key '{name}' must be {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )

    return value
