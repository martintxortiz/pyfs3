import queue
import time
import unittest

from fsw import ExecutiveServices, Message


class WatchdogTests(unittest.TestCase):
    def test_watchdog_publishes_alert_when_heartbeat_times_out(self):
        es = ExecutiveServices.from_dict(
            {
                "apps": [
                    {
                        "name": "Watchdog",
                        "class": "fsw.apps.watchdog.WatchdogApp",
                        "config": {
                            "heartbeat_topic": "heartbeat/ground_link",
                            "timeout_seconds": 0.1,
                            "alert_topic": "alerts/out",
                            "alert_message": "GROUND_LINK_TIMEOUT",
                            "alert_min_interval_seconds": 0.1,
                            "poll_seconds": 0.02,
                        },
                    }
                ]
            }
        )
        inbox = es.bus.subscribe("alerts/out")

        with self.assertLogs("Watchdog", level="WARNING"):
            es.start()
            try:
                alert = self._wait_for_message(inbox)
            finally:
                es.stop()

        self.assertEqual(alert.payload, "GROUND_LINK_TIMEOUT")

    def test_heartbeat_delays_watchdog_alert(self):
        es = ExecutiveServices.from_dict(
            {
                "apps": [
                    {
                        "name": "Watchdog",
                        "class": "fsw.apps.watchdog.WatchdogApp",
                        "config": {
                            "heartbeat_topic": "heartbeat/ground_link",
                            "timeout_seconds": 0.2,
                            "alert_topic": "alerts/out",
                            "alert_message": "GROUND_LINK_TIMEOUT",
                            "alert_min_interval_seconds": 0.2,
                            "poll_seconds": 0.02,
                        },
                    }
                ]
            }
        )
        inbox = es.bus.subscribe("alerts/out")

        with self.assertLogs("Watchdog", level="WARNING"):
            es.start()
            try:
                time.sleep(0.1)
                es.bus.publish(Message(topic="heartbeat/ground_link", payload="ok"))
                with self.assertRaises(queue.Empty):
                    inbox.get(timeout=0.05)
                alert = self._wait_for_message(inbox)
            finally:
                es.stop()

        self.assertEqual(alert.payload, "GROUND_LINK_TIMEOUT")

    def test_watchdog_repeats_alert_while_breached(self):
        es = ExecutiveServices.from_dict(
            {
                "apps": [
                    {
                        "name": "Watchdog",
                        "class": "fsw.apps.watchdog.WatchdogApp",
                        "config": {
                            "timeout_seconds": 0.1,
                            "alert_topic": "alerts/out",
                            "alert_message": "TIMEOUT",
                            "alert_min_interval_seconds": 0.1,
                            "poll_seconds": 0.02,
                        },
                    }
                ]
            }
        )
        inbox = es.bus.subscribe("alerts/out")

        with self.assertLogs("Watchdog", level="WARNING"):
            es.start()
            try:
                first = self._wait_for_message(inbox)
                second = self._wait_for_message(inbox)
            finally:
                es.stop()

        self.assertEqual(first.payload, "TIMEOUT")
        self.assertEqual(second.payload, "TIMEOUT")

    def test_watchdog_alert_is_rate_limited(self):
        es = ExecutiveServices.from_dict(
            {
                "apps": [
                    {
                        "name": "Watchdog",
                        "class": "fsw.apps.watchdog.WatchdogApp",
                        "config": {
                            "timeout_seconds": 0.05,
                            "alert_topic": "alerts/out",
                            "alert_message": "TIMEOUT",
                            "alert_min_interval_seconds": 0.3,
                            "poll_seconds": 0.01,
                        },
                    }
                ]
            }
        )
        inbox = es.bus.subscribe("alerts/out")

        with self.assertLogs("Watchdog", level="WARNING"):
            es.start()
            try:
                first = self._wait_for_message(inbox)
                with self.assertRaises(queue.Empty):
                    inbox.get(timeout=0.1)
            finally:
                es.stop()

        self.assertEqual(first.payload, "TIMEOUT")

    def _wait_for_message(self, inbox):
        deadline = time.time() + 1.0
        while time.time() < deadline:
            try:
                return inbox.get(timeout=0.05)
            except queue.Empty:
                continue
        self.fail("No watchdog alert received")


if __name__ == "__main__":
    unittest.main()
