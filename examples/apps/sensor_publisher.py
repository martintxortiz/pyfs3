import random
from dataclasses import dataclass

from fsw import Message, Node


@dataclass(frozen=True)
class SensorPublisherConfig:
    topic: str = "telemetry/out"
    interval_seconds: float = 1.0
    min_value: float = 0.0
    max_value: float = 100.0


class SensorPublisherApp(Node):
    """Publishes a random sensor reading at a fixed interval."""

    def init(self) -> None:
        self.settings = self.load_config(SensorPublisherConfig)

    def run(self) -> None:
        while not self._stop_event.is_set():
            value = random.uniform(self.settings.min_value, self.settings.max_value)
            self.bus.publish(Message(
                topic=self.settings.topic,
                payload=f"sensor/value {value:.2f}",
            ))
            self._stop_event.wait(timeout=self.settings.interval_seconds)
