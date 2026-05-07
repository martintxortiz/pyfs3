from dataclasses import dataclass

from fsw import Node


@dataclass(frozen=True)
class SubscriberConfig:
    topic: str = "sensor/random_value"
    poll_timeout: float = 0.5


class SubscriberApp(Node):
    """Receives and logs random float messages."""

    def init(self) -> None:
        self.settings = self.load_config(SubscriberConfig)
        self._inbox = self.subscribe(self.settings.topic)
        self.log.info("SubscriberApp initialized; subscribed to '%s'", self.settings.topic)

    def run(self) -> None:
        while not self._stop_event.is_set():
            msg = self.get_message(self._inbox, self.settings.poll_timeout)
            if msg is None:
                continue

            self.log.info(
                "[%s] value=%.4f ts=%.3f",
                msg.topic,
                msg.payload,
                msg.timestamp,
            )

    def shutdown(self) -> None:
        self.log.info("SubscriberApp shutting down")
