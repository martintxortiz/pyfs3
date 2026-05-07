import queue
import socket
import time
import unittest

from fsw import ExecutiveServices, Message


class UdpCommsTests(unittest.TestCase):
    def test_ground_command_gets_flight_sensor_response(self):
        flight_port = self._free_udp_port()
        ground_port = self._free_udp_port()

        flight = ExecutiveServices.from_dict(
            {
                "apps": [
                    {
                        "name": "FlightCommandIngest",
                        "class": "fsw.apps.command_ingest.CommandIngestApp",
                        "priority": 10,
                        "config": {
                            "bind_port": flight_port,
                            "output_topic": "commands/in",
                        },
                    },
                    {
                        "name": "FlightTelemetryOutput",
                        "class": "fsw.apps.telemetry_output.TelemetryOutputApp",
                        "priority": 20,
                        "config": {
                            "remote_port": ground_port,
                            "input_topic": "telemetry/out",
                        },
                    },
                    {
                        "name": "FlightSensor",
                        "class": "test_comms.apps.sensor_app.SensorApp",
                        "priority": 30,
                    },
                ]
            }
        )
        ground = ExecutiveServices.from_dict(
            {
                "apps": [
                    {
                        "name": "GroundCommandIngest",
                        "class": "fsw.apps.command_ingest.CommandIngestApp",
                        "priority": 10,
                        "config": {
                            "bind_port": ground_port,
                            "output_topic": "commands/in",
                        },
                    },
                    {
                        "name": "GroundTelemetryOutput",
                        "class": "fsw.apps.telemetry_output.TelemetryOutputApp",
                        "priority": 20,
                        "config": {
                            "remote_port": flight_port,
                            "input_topic": "telemetry/out",
                        },
                    },
                ]
            }
        )
        ground_inbox = ground.bus.subscribe("commands/in")

        flight.start()
        ground.start()
        try:
            ground.bus.publish(Message(topic="telemetry/out", payload="sensor/get_value"))
            response = self._wait_for_message(ground_inbox)
        finally:
            ground.stop()
            flight.stop()

        self.assertTrue(response.payload.startswith("sensor/value "))

    def test_arbitrary_text_can_be_sent_between_sides(self):
        flight_port = self._free_udp_port()
        ground_port = self._free_udp_port()
        flight = self._one_way_side("Flight", flight_port, ground_port)
        ground = self._one_way_side("Ground", ground_port, flight_port)
        flight_inbox = flight.bus.subscribe("commands/in")

        flight.start()
        ground.start()
        try:
            ground.bus.publish(Message(topic="telemetry/out", payload="hello flight"))
            response = self._wait_for_message(flight_inbox)
        finally:
            ground.stop()
            flight.stop()

        self.assertEqual(response.payload, "hello flight")

    def _one_way_side(self, name: str, bind_port: int, remote_port: int):
        return ExecutiveServices.from_dict(
            {
                "apps": [
                    {
                        "name": f"{name}CommandIngest",
                        "class": "fsw.apps.command_ingest.CommandIngestApp",
                        "priority": 10,
                        "config": {
                            "bind_port": bind_port,
                            "output_topic": "commands/in",
                        },
                    },
                    {
                        "name": f"{name}TelemetryOutput",
                        "class": "fsw.apps.telemetry_output.TelemetryOutputApp",
                        "priority": 20,
                        "config": {
                            "remote_port": remote_port,
                            "input_topic": "telemetry/out",
                        },
                    },
                ]
            }
        )

    def _wait_for_message(self, inbox):
        deadline = time.time() + 2.0
        while time.time() < deadline:
            try:
                return inbox.get(timeout=0.1)
            except queue.Empty:
                continue
        self.fail("No UDP message received")

    def _free_udp_port(self) -> int:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]
        finally:
            sock.close()


if __name__ == "__main__":
    unittest.main()
