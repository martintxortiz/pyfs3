import queue
import threading
from dataclasses import dataclass

from fsw import Message, Node


@dataclass(frozen=True)
class TerminalBridgeConfig:
    input_topic: str = "commands/in"
    output_topic: str = "telemetry/out"
    prompt: str = "> "
    timeout_seconds: float = 0.2


class TerminalBridgeApp(Node):
    """Prints received bus text and publishes terminal input."""

    def init(self) -> None:
        self.settings = self.load_config(TerminalBridgeConfig)
        self.inbox = self.subscribe(self.settings.input_topic)
        self.lines: queue.Queue[str] = queue.Queue()
        self.reader = threading.Thread(target=self._read_terminal, daemon=True)
        self.reader.start()
        self.log.info("Terminal bridge ready")

    def run(self) -> None:
        while not self._stop_event.is_set():
            self._print_received()
            self._send_typed_lines()

    def _print_received(self) -> None:
        msg = self.get_message(self.inbox, self.settings.timeout_seconds)
        if msg is None:
            return

        print(msg.payload)

    def _send_typed_lines(self) -> None:
        while True:
            try:
                line = self.lines.get_nowait()
            except queue.Empty:
                return

            if line:
                self.bus.publish(Message(topic=self.settings.output_topic, payload=line))

    def _read_terminal(self) -> None:
        while not self._stop_event.is_set():
            try:
                line = input(self.settings.prompt)
            except EOFError:
                return
            self.lines.put(line)
