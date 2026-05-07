import random
from dataclasses import dataclass

from fsw import Message, Node


@dataclass(frozen=True)
class PublisherConfig:
    topic: str = "sensor/random_value"
    rate_hz: float = 2.0
    min_value: float = 0.0
    max_value: float = 100.0


class PublisherApp(Node):
    """Publishes a random float at a fixed rate."""

    def init(self) -> None:
        self.settings = self.load_config(PublisherConfig)
        self.log.info("PublisherApp initialized")

    def run(self) -> None:
        interval = 1.0 / self.settings.rate_hz
        while not self._stop_event.is_set():
            value = random.uniform(self.settings.min_value, self.settings.max_value)
            self.bus.publish(Message(topic=self.settings.topic, payload=value))
            self.log.debug("Published: %.4f", value)
            self._stop_event.wait(timeout=interval)

    def shutdown(self) -> None:
        self.log.info("PublisherApp shutting down")
