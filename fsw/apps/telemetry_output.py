import socket
from dataclasses import dataclass

from fsw import Node


@dataclass(frozen=True)
class TelemetryOutputConfig:
    remote_host: str = "127.0.0.1"
    remote_port: int = 5001
    input_topic: str = "telemetry/out"
    timeout_seconds: float = 0.2


class TelemetryOutputApp(Node):
    """Sends bus messages as UDP text telemetry."""

    def init(self) -> None:
        self.settings = self.load_config(TelemetryOutputConfig)
        self.inbox = self.subscribe(self.settings.input_topic)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.log.info(
            "Telemetry output sending to %s:%s",
            self.settings.remote_host,
            self.settings.remote_port,
        )

    def run(self) -> None:
        target = (self.settings.remote_host, self.settings.remote_port)
        while not self._stop_event.is_set():
            msg = self.get_message(self.inbox, self.settings.timeout_seconds)
            if msg is None:
                continue
            self.sock.sendto(str(msg.payload).encode("utf-8"), target)
            self.log.info("TX %s", msg.payload)

    def shutdown(self) -> None:
        self.sock.close()
        self.log.info("Telemetry output shutting down")
