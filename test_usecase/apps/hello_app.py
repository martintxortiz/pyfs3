from dataclasses import dataclass

from fsw import Node


@dataclass(frozen=True)
class HelloConfig:
    message: str = "hello"
    interval_seconds: float = 1.0


class HelloApp(Node):
    """Prints a configured message at a fixed interval."""

    def init(self) -> None:
        self.settings = self.load_config(HelloConfig)
        self.log.info("HelloApp initialized")

    def run(self) -> None:
        while not self._stop_event.is_set():
            self.log.info(self.settings.message)
            self._stop_event.wait(timeout=self.settings.interval_seconds)

    def shutdown(self) -> None:
        self.log.info("HelloApp shutting down")
