import queue
import unittest

from fsw import Message, SoftwareBus


class SoftwareBusTests(unittest.TestCase):
    def test_publish_routes_message_to_matching_topic(self):
        bus = SoftwareBus()
        inbox = bus.subscribe("sensor/test")
        msg = Message(topic="sensor/test", payload=42)

        bus.publish(msg)

        self.assertIs(inbox.get_nowait(), msg)

    def test_subscribers_have_isolated_queues(self):
        bus = SoftwareBus()
        first = bus.subscribe("sensor/test")
        second = bus.subscribe("sensor/test")
        msg = Message(topic="sensor/test", payload=42)

        bus.publish(msg)

        self.assertIs(first.get_nowait(), msg)
        self.assertIs(second.get_nowait(), msg)
        self.assertIsNot(first, second)

    def test_publish_ignores_unmatched_topics(self):
        bus = SoftwareBus()
        inbox = bus.subscribe("sensor/other")

        bus.publish(Message(topic="sensor/test", payload=42))

        with self.assertRaises(queue.Empty):
            inbox.get_nowait()

    def test_full_queue_drop_does_not_raise(self):
        bus = SoftwareBus(maxsize=1)
        inbox = bus.subscribe("sensor/test")

        bus.publish(Message(topic="sensor/test", payload=1))
        with self.assertLogs("fsw.software_bus", level="WARNING"):
            bus.publish(Message(topic="sensor/test", payload=2))

        self.assertEqual(inbox.get_nowait().payload, 1)
        with self.assertRaises(queue.Empty):
            inbox.get_nowait()

    def test_unsubscribe_removes_one_queue(self):
        bus = SoftwareBus()
        first = bus.subscribe("sensor/test")
        second = bus.subscribe("sensor/test")

        bus.unsubscribe("sensor/test", first)
        bus.publish(Message(topic="sensor/test", payload=42))

        with self.assertRaises(queue.Empty):
            first.get_nowait()
        self.assertEqual(second.get_nowait().payload, 42)


if __name__ == "__main__":
    unittest.main()
