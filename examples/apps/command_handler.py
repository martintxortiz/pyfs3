from dataclasses import dataclass

from fsw import Message, Node


@dataclass(frozen=True)
class CommandHandlerConfig:
    input_topic: str = "commands/in"
    telemetry_topic: str = "telemetry/out"
    heartbeat_topic: str = "heartbeat/ground_link"
    ping_command: str = "ping"
    pong_reply: str = "pong"
    heartbeat_command: str = "heartbeat"
    timeout_seconds: float = 0.2


class CommandHandlerApp(Node):
    """Routes incoming ground commands: ping->pong, heartbeat->watchdog topic."""

    def init(self) -> None:
        self.settings = self.load_config(CommandHandlerConfig)
        self.inbox = self.subscribe(self.settings.input_topic)

    def run(self) -> None:
        while not self._stop_event.is_set():
            msg = self.get_message(self.inbox, self.settings.timeout_seconds)
            if msg is None:
                continue
            if msg.payload == self.settings.ping_command:
                self.bus.publish(Message(
                    topic=self.settings.telemetry_topic,
                    payload=self.settings.pong_reply,
                ))
            elif msg.payload == self.settings.heartbeat_command:
                # Forward heartbeats onto the watchdog's dedicated topic so the
                # CommandIngest topic stays a single channel for raw UDP text.
                self.bus.publish(Message(
                    topic=self.settings.heartbeat_topic,
                    payload=msg.payload,
                ))
