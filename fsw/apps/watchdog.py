import time
from dataclasses import dataclass

from fsw import Node


@dataclass(frozen=True)
class WatchdogConfig:
    heartbeat_topic: str = "heartbeat/ground_link"
    timeout_seconds: float = 10.0
    alert_topic: str = "telemetry/out"
    alert_message: str = "WATCHDOG_TIMEOUT"
    alert_min_interval_seconds: float = 10.0
    poll_seconds: float = 0.2


class WatchdogApp(Node):
    """Publishes an alert if a heartbeat topic goes quiet."""

    def init(self) -> None:
        self.settings = self.load_config(WatchdogConfig)
        self.inbox = self.subscribe(self.settings.heartbeat_topic)
        self.last_heartbeat = time.monotonic()
        self.log.info("Watchdog monitoring %s", self.settings.heartbeat_topic)

    def run(self) -> None:
        while not self._stop_event.is_set():
            self._check_heartbeat()
            self._check_timeout()

    def _check_heartbeat(self) -> None:
        msg = self.get_message(self.inbox, self.settings.poll_seconds)
        if msg is None:
            return

        self.last_heartbeat = time.monotonic()

    def _check_timeout(self) -> None:
        now = time.monotonic()
        if now - self.last_heartbeat < self.settings.timeout_seconds:
            return

        sent = self.emit_event(
            topic=self.settings.alert_topic,
            payload=self.settings.alert_message,
            min_interval_seconds=self.settings.alert_min_interval_seconds,
        )
        if sent:
            self.log.warning(self.settings.alert_message)
