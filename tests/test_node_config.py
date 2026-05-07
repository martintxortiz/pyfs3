from dataclasses import dataclass, field
import threading
import unittest

from fsw import ExecutiveServices, Node, NodeState
from fsw.software_bus import SoftwareBus


@dataclass(frozen=True)
class ExampleConfig:
    message: str = "hello"
    interval_seconds: float = 1.0


@dataclass(frozen=True)
class RequiredFieldConfig:
    threshold: int


@dataclass(frozen=True)
class FactoryConfig:
    tags: list[str] = field(default_factory=list)


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


class _StaticNode(Node):
    """Minimal node used to exercise load_config directly without the lifecycle."""

    def run(self) -> None:
        self._stop_event.wait(timeout=0.0)


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
        self.assertIn("must be float", node.last_error)

    def test_load_config_rejects_non_dataclass_type(self):
        node = _StaticNode("Static", SoftwareBus())

        with self.assertRaisesRegex(TypeError, "config_type must be a dataclass"):
            node.load_config(dict)  # type: ignore[arg-type]

    def test_load_config_raises_when_required_field_missing(self):
        node = _StaticNode("Static", SoftwareBus(), config={})

        with self.assertRaisesRegex(ValueError, "Missing required config key: threshold"):
            node.load_config(RequiredFieldConfig)

    def test_load_config_coerces_int_to_float(self):
        node = _StaticNode("Static", SoftwareBus(), config={"interval_seconds": 2})

        loaded = node.load_config(ExampleConfig)

        # An int provided where a float is expected must be coerced, not rejected.
        self.assertEqual(loaded.interval_seconds, 2.0)
        self.assertIsInstance(loaded.interval_seconds, float)

    def test_load_config_rejects_bool_passed_for_float(self):
        node = _StaticNode("Static", SoftwareBus(), config={"interval_seconds": True})

        # bool inherits from int in Python; the framework must guard the
        # int->float coercion path so a stray boolean does not slip through.
        with self.assertRaisesRegex(ValueError, "interval_seconds.*must be float"):
            node.load_config(ExampleConfig)

    def test_load_config_uses_default_factory_when_field_absent(self):
        node = _StaticNode("Static", SoftwareBus(), config={})

        loaded = node.load_config(FactoryConfig)

        self.assertEqual(loaded.tags, [])
        # Each call must produce its own instance from the factory.
        self.assertIsNot(loaded.tags, node.load_config(FactoryConfig).tags)


if __name__ == "__main__":
    unittest.main()
