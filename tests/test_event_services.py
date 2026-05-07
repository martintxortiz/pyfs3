import queue
import time
import unittest

from fsw import EventServices, SoftwareBus


class EventServicesTests(unittest.TestCase):
    def test_emit_publishes_event_message(self):
        bus = SoftwareBus()
        events = EventServices(bus)
        inbox = bus.subscribe("events/out")

        sent = events.emit("events/out", "LINK_TIMEOUT")

        self.assertTrue(sent)
        self.assertEqual(inbox.get_nowait().payload, "LINK_TIMEOUT")

    def test_emit_rate_limits_same_event_key(self):
        bus = SoftwareBus()
        events = EventServices(bus)
        inbox = bus.subscribe("events/out")

        first = events.emit("events/out", "LINK_TIMEOUT", 10.0)
        second = events.emit("events/out", "LINK_TIMEOUT", 10.0)

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(inbox.get_nowait().payload, "LINK_TIMEOUT")
        with self.assertRaises(queue.Empty):
            inbox.get_nowait()

    def test_emit_allows_event_after_interval(self):
        bus = SoftwareBus()
        events = EventServices(bus)
        inbox = bus.subscribe("events/out")

        events.emit("events/out", "LINK_TIMEOUT", 0.05)
        time.sleep(0.06)
        sent = events.emit("events/out", "LINK_TIMEOUT", 0.05)

        self.assertTrue(sent)
        self.assertEqual(inbox.get_nowait().payload, "LINK_TIMEOUT")
        self.assertEqual(inbox.get_nowait().payload, "LINK_TIMEOUT")

    def test_emit_with_zero_interval_never_rate_limits(self):
        bus = SoftwareBus()
        events = EventServices(bus)
        inbox = bus.subscribe("events/out")

        for _ in range(5):
            self.assertTrue(events.emit("events/out", "TICK", 0.0))

        for _ in range(5):
            self.assertEqual(inbox.get_nowait().payload, "TICK")
        with self.assertRaises(queue.Empty):
            inbox.get_nowait()

    def test_emit_rate_limits_independently_per_event_key(self):
        bus = SoftwareBus()
        events = EventServices(bus)
        inbox = bus.subscribe("events/out")

        first = events.emit("events/out", "ALERT_A", 10.0)
        second = events.emit("events/out", "ALERT_B", 10.0)

        # Different (topic, payload) keys must not share the same rate-limit budget.
        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(inbox.get_nowait().payload, "ALERT_A")
        self.assertEqual(inbox.get_nowait().payload, "ALERT_B")

    def test_explicit_key_overrides_default_topic_payload_key(self):
        bus = SoftwareBus()
        events = EventServices(bus)
        bus.subscribe("events/out")

        first = events.emit("events/out", "ALERT", 10.0, key="watchdog/A")
        # Same topic and payload, but a different explicit key, must not be rate-limited.
        second = events.emit("events/out", "ALERT", 10.0, key="watchdog/B")
        # Same explicit key, same topic and payload, must be rate-limited.
        third = events.emit("events/out", "ALERT", 10.0, key="watchdog/A")

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertFalse(third)


if __name__ == "__main__":
    unittest.main()
