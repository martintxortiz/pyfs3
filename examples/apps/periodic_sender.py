from dataclasses import dataclass

from fsw import Message, Node


@dataclass(frozen=True)
class PeriodicSenderConfig:
    topic: str = "telemetry/out"
    message: str = "ping"
    interval_seconds: float = 1.0


class PeriodicSenderApp(Node):
    """Publishes a fixed payload to a topic at a fixed interval."""

    def init(self) -> None:
        self.settings = self.load_config(PeriodicSenderConfig)

    def run(self) -> None:
        while not self._stop_event.is_set():
            self.bus.publish(Message(
                topic=self.settings.topic,
                payload=self.settings.message,
            ))
            self._stop_event.wait(timeout=self.settings.interval_seconds)
