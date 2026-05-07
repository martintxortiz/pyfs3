import random
from dataclasses import dataclass

from fsw import Message, Node


@dataclass(frozen=True)
class SensorConfig:
    input_topic: str = "commands/in"
    output_topic: str = "telemetry/out"
    command: str = "sensor/get_value"
    timeout_seconds: float = 0.2


class SensorApp(Node):
    """Responds to a simple sensor command."""

    def init(self) -> None:
        self.settings = self.load_config(SensorConfig)
        self.inbox = self.subscribe(self.settings.input_topic)
        self.log.info("Sensor app ready")

    def run(self) -> None:
        while not self._stop_event.is_set():
            msg = self.get_message(self.inbox, self.settings.timeout_seconds)
            if msg is None or msg.payload != self.settings.command:
                continue
            value = random.uniform(0.0, 100.0)
            self.bus.publish(Message(
                topic=self.settings.output_topic,
                payload=f"sensor/value {value:.2f}",
            ))

    def shutdown(self) -> None:
        self.log.info("Sensor app shutting down")
