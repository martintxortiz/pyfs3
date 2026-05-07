import time
import unittest

from fsw import Message


class MessageTests(unittest.TestCase):
    def test_message_stores_topic_payload_and_timestamp(self):
        before = time.time()
        msg = Message(topic="sensor/test", payload={"value": 10})
        after = time.time()

        self.assertEqual(msg.topic, "sensor/test")
        self.assertEqual(msg.payload, {"value": 10})
        self.assertGreaterEqual(msg.timestamp, before)
        self.assertLessEqual(msg.timestamp, after)


if __name__ == "__main__":
    unittest.main()
