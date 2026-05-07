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


if __name__ == "__main__":
    unittest.main()
