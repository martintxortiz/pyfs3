import queue
import threading
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

    def test_unsubscribe_unknown_topic_is_silently_ignored(self):
        bus = SoftwareBus()
        inbox: queue.Queue[Message] = queue.Queue()

        # Must not raise when topic was never subscribed to.
        bus.unsubscribe("never/seen", inbox)

    def test_unsubscribe_unknown_inbox_is_silently_ignored(self):
        bus = SoftwareBus()
        bus.subscribe("sensor/test")
        stranger: queue.Queue[Message] = queue.Queue()

        # Must not raise when the inbox was never registered for the topic.
        bus.unsubscribe("sensor/test", stranger)

    def test_unsubscribe_drops_topic_when_last_subscriber_leaves(self):
        bus = SoftwareBus()
        inbox = bus.subscribe("sensor/test")

        bus.unsubscribe("sensor/test", inbox)

        # Topic key is removed so the bus does not retain empty subscriber lists.
        self.assertNotIn("sensor/test", bus._subscribers)

    def test_concurrent_publish_and_subscribe_remain_thread_safe(self):
        bus = SoftwareBus(maxsize=10000)
        publisher_count = 4
        per_publisher = 250
        inbox = bus.subscribe("sensor/test")

        def publish_many() -> None:
            for i in range(per_publisher):
                bus.publish(Message(topic="sensor/test", payload=i))

        threads = [threading.Thread(target=publish_many) for _ in range(publisher_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        received = 0
        while True:
            try:
                inbox.get_nowait()
                received += 1
            except queue.Empty:
                break
        self.assertEqual(received, publisher_count * per_publisher)


if __name__ == "__main__":
    unittest.main()
