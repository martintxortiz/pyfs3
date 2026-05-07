from dataclasses import dataclass
import threading
import unittest

from fsw import ExecutiveServices, Node, NodeState


@dataclass(frozen=True)
class ExampleConfig:
    message: str = "hello"
    interval_seconds: float = 1.0


class ConfigNode(Node):
    def __init__(self, name, bus, config=None):
        super().__init__(name, bus, config=config)
        self.loaded_config: ExampleConfig | None = None
        self.started = threading.Event()

    def init(self) -> None:
        self.loaded_config = self.load_config(ExampleConfig)

    def run(self) -> None:
        self.started.set()
        self._stop_event.wait(timeout=1.0)


class NodeConfigTests(unittest.TestCase):
    def test_load_config_uses_typed_dataclass_defaults(self):
        es = ExecutiveServices()
        node = ConfigNode("ConfigNode", es.bus, config={"message": "hi"})

        es.register(node)
        es.start()
        self.assertTrue(node.started.wait(timeout=1.0))
        es.stop()

        self.assertEqual(node.loaded_config, ExampleConfig(message="hi"))

    def test_load_config_warns_for_unused_keys(self):
        es = ExecutiveServices()
        node = ConfigNode("ConfigNode", es.bus, config={"unused": 1})

        es.register(node)
        with self.assertLogs("ConfigNode", level="WARNING") as logs:
            es.start()
        es.stop()

        self.assertIn("Unused config key ignored: unused", "\n".join(logs.output))

    def test_load_config_rejects_wrong_value_type(self):
        es = ExecutiveServices()
        node = ConfigNode("ConfigNode", es.bus, config={"interval_seconds": "fast"})

        es.register(node)
        with self.assertLogs("fsw.node", level="ERROR"):
            es.start()

        self.assertEqual(node.state, NodeState.FAILED)
        self.assertIn("interval_seconds", node.last_error)


if __name__ == "__main__":
    unittest.main()
