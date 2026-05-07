import threading
import time
import unittest

from fsw import EventServices, ExecutiveServices, Node, NodeState


class TestNode(Node):
    def __init__(self, name, bus):
        super().__init__(name, bus)
        self.events: list[str] = []
        self.started = threading.Event()

    def init(self) -> None:
        self.events.append("init")

    def run(self) -> None:
        self.events.append("run")
        self.started.set()
        self._stop_event.wait(timeout=1.0)

    def shutdown(self) -> None:
        self.events.append("shutdown")


class InitFailNode(TestNode):
    def init(self) -> None:
        self.events.append("init")
        raise RuntimeError("init failed")


class CrashNode(TestNode):
    def run(self) -> None:
        self.events.append("run")
        self.started.set()
        raise RuntimeError("run failed")


class _MinimalNode(Node):
    """A bare Node subclass that does not override ``events`` for lifecycle tracking."""

    def run(self) -> None:
        self._stop_event.wait(timeout=0.0)


class ExecutiveServicesTests(unittest.TestCase):
    def test_register_start_and_stop_node_lifecycle(self):
        es = ExecutiveServices()
        node = TestNode(name="TestNode", bus=es.bus)

        es.register(node)
        es.start()
        self.assertTrue(node.started.wait(timeout=1.0))
        es.stop()

        self.assertEqual(node.events, ["init", "run", "shutdown"])
        self.assertIs(node.state, NodeState.STOPPED)

    def test_register_rejects_duplicate_node_names(self):
        es = ExecutiveServices()

        es.register(TestNode(name="TestNode", bus=es.bus))
        with self.assertRaisesRegex(ValueError, "Node already registered"):
            es.register(TestNode(name="TestNode", bus=es.bus))

    def test_start_uses_priority_and_skips_disabled_nodes(self):
        es = ExecutiveServices()
        events = []

        class PriorityNode(TestNode):
            def init(self) -> None:
                events.append(self.name)
                super().init()

        low = PriorityNode(name="Low", bus=es.bus)
        high = PriorityNode(name="High", bus=es.bus)
        disabled = PriorityNode(name="Disabled", bus=es.bus)

        es.register(low, priority=20)
        es.register(high, priority=10)
        es.register(disabled, priority=1, enabled=False)
        es.start()
        self.assertTrue(low.started.wait(timeout=1.0))
        self.assertTrue(high.started.wait(timeout=1.0))
        es.stop()

        self.assertEqual(events, ["High", "Low"])
        self.assertEqual(disabled.events, [])

    def test_restart_node_stops_and_starts_one_node(self):
        es = ExecutiveServices()
        node = TestNode(name="TestNode", bus=es.bus)

        es.register(node)
        es.start()
        self.assertTrue(node.started.wait(timeout=1.0))
        node.started.clear()
        es.restart_node("TestNode")
        self.assertTrue(node.started.wait(timeout=1.0))
        es.stop()

        self.assertEqual(node.events, ["init", "run", "shutdown", "init", "run", "shutdown"])

    def test_start_failure_does_not_block_other_nodes(self):
        es = ExecutiveServices()
        bad = InitFailNode(name="BadNode", bus=es.bus)
        good = TestNode(name="GoodNode", bus=es.bus)

        es.register(bad, priority=10)
        es.register(good, priority=20)
        with self.assertLogs("fsw.node", level="ERROR"):
            es.start()
        self.assertTrue(good.started.wait(timeout=1.0))
        es.stop()

        health = es.health()
        self.assertEqual(health["BadNode"]["state"], NodeState.FAILED.value)
        self.assertIn("init failed", health["BadNode"]["error"])
        self.assertEqual(good.events, ["init", "run", "shutdown"])

    def test_run_loop_crash_is_reported_without_crashing_es(self):
        es = ExecutiveServices()
        bad = CrashNode(name="CrashNode", bus=es.bus)
        good = TestNode(name="GoodNode", bus=es.bus)

        es.register(bad, priority=10)
        es.register(good, priority=20)
        with self.assertLogs("fsw.node", level="ERROR"):
            es.start()
            self.assertTrue(bad.started.wait(timeout=1.0))
            self.assertTrue(good.started.wait(timeout=1.0))
            self._wait_for_state(bad, NodeState.FAILED)
        es.stop()

        health = es.health()
        self.assertEqual(health["CrashNode"]["state"], NodeState.FAILED.value)
        self.assertIn("run failed", health["CrashNode"]["error"])
        self.assertEqual(good.events, ["init", "run", "shutdown"])

    def test_faulted_config_app_is_reported_in_health(self):
        with self.assertLogs("fsw", level="ERROR"):
            es = ExecutiveServices.from_dict(
                {
                    "apps": [
                        {
                            "name": "BadApp",
                            "class": "examples.apps.missing.MissingApp",
                        },
                        {
                            "name": "GoodApp",
                            "class": "examples.apps.hello_app.HelloApp",
                            "enabled": False,
                        },
                    ]
                }
            )

        health = es.health()

        self.assertEqual(health["BadApp"]["state"], NodeState.FAILED.value)
        self.assertIn("No module named", health["BadApp"]["error"])
        self.assertEqual(health["GoodApp"]["state"], NodeState.CREATED.value)

    def test_stop_node_only_stops_the_named_node(self):
        es = ExecutiveServices()
        first = TestNode(name="First", bus=es.bus)
        second = TestNode(name="Second", bus=es.bus)

        es.register(first)
        es.register(second)
        es.start()
        try:
            self.assertTrue(first.started.wait(timeout=1.0))
            self.assertTrue(second.started.wait(timeout=1.0))
            es.stop_node("First")

            self.assertIs(first.state, NodeState.STOPPED)
            self.assertIs(second.state, NodeState.RUNNING)
            self.assertEqual(first.events, ["init", "run", "shutdown"])
        finally:
            es.stop()

    def test_stop_node_with_unknown_name_raises_key_error(self):
        es = ExecutiveServices()

        with self.assertRaisesRegex(KeyError, "No node named Ghost"):
            es.stop_node("Ghost")

    def test_restart_node_with_unknown_name_raises_key_error(self):
        es = ExecutiveServices()

        with self.assertRaisesRegex(KeyError, "No node named Ghost"):
            es.restart_node("Ghost")

    def test_restart_node_skipped_when_disabled(self):
        es = ExecutiveServices()
        node = TestNode(name="Disabled", bus=es.bus)

        es.register(node, enabled=False)
        es.start()
        try:
            es.restart_node("Disabled")
        finally:
            es.stop()

        # Disabled node must never have run init/run/shutdown.
        self.assertEqual(node.events, [])
        self.assertIs(node.state, NodeState.CREATED)

    def test_register_injects_executive_event_services_when_node_has_none(self):
        es = ExecutiveServices()
        node = _MinimalNode(name="MinNode", bus=es.bus)
        self.assertIsNone(node.events)

        es.register(node)

        # ExecutiveServices must wire its own EventServices into nodes that lack one,
        # so emit_event() goes through the rate-limited path.
        self.assertIs(node.events, es.events)

    def test_register_preserves_existing_event_services_on_node(self):
        es = ExecutiveServices()
        external = EventServices(es.bus)
        node = _MinimalNode(name="MinNode", bus=es.bus, events=external)

        es.register(node)

        self.assertIs(node.events, external)

    def _wait_for_state(self, node: Node, state: NodeState) -> None:
        deadline = time.time() + 1.0
        while time.time() < deadline:
            if node.state is state:
                return
            time.sleep(0.01)
        self.fail(f"{node.name} did not reach state {state.value}")


if __name__ == "__main__":
    unittest.main()
