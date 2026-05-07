import socket
from dataclasses import dataclass

from fsw import Message, Node


@dataclass(frozen=True)
class CommandIngestConfig:
    bind_host: str = "127.0.0.1"
    bind_port: int = 5000
    output_topic: str = "commands/in"
    timeout_seconds: float = 0.2


class CommandIngestApp(Node):
    """Receives UDP text commands and publishes them on the bus."""

    def init(self) -> None:
        self.settings = self.load_config(CommandIngestConfig)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind((self.settings.bind_host, self.settings.bind_port))
        except OSError:
            self.sock.close()
            raise
        self.sock.settimeout(self.settings.timeout_seconds)
        self.log.info(
            "Command ingest listening on %s:%s",
            self.settings.bind_host,
            self.settings.bind_port,
        )

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                data, address = self.sock.recvfrom(4096)
            except TimeoutError:
                continue

            text = data.decode("utf-8", errors="replace").strip()
            if text:
                self.log.info("RX from %s:%s %s", address[0], address[1], text)
                self.bus.publish(Message(topic=self.settings.output_topic, payload=text))

    def shutdown(self) -> None:
        self.sock.close()
        self.log.info("Command ingest shutting down")
