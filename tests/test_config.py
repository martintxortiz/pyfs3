import logging
import unittest

from fsw import (
    ExecutiveServices,
    configure_logging,
    load_env,
    load_system_config,
    load_yaml,
    parse_system_config,
)


class ConfigTests(unittest.TestCase):
    def test_load_yaml_reads_simple_values_and_lists(self):
        data = load_yaml("test_usecase/config/system.yml")

        self.assertEqual(data["bus"]["maxsize"], 100)
        self.assertEqual(data["apps"][0]["name"], "SubscriberApp")
        self.assertTrue(data["apps"][0]["enabled"])

    def test_load_system_config_loads_app_classes_and_app_config(self):
        config = load_system_config("test_usecase/config/system.yml")

        self.assertEqual(config["bus_maxsize"], 100)
        self.assertEqual(config["logging"]["level"], "INFO")
        self.assertEqual(config["apps"][0]["name"], "SubscriberApp")
        self.assertEqual(config["apps"][0]["config"]["topic"], "sensor/random_value")
        self.assertTrue(callable(config["apps"][0]["class"]))

    def test_executive_services_can_be_created_from_config(self):
        es = ExecutiveServices.from_config("test_usecase/config/system.yml")

        self.assertEqual(len(es._nodes), 3)
        self.assertEqual(es._nodes[0].node.name, "SubscriberApp")

    def test_parse_system_config_accepts_inline_app_config(self):
        config = parse_system_config(
            {
                "apps": [
                    {
                        "name": "HelloApp",
                        "class": "test_usecase.apps.hello_app.HelloApp",
                        "config": {
                            "message": "hi",
                            "interval_seconds": 0.1,
                        },
                    }
                ]
            }
        )

        self.assertEqual(config["apps"][0]["config"]["message"], "hi")

    def test_from_dict_builds_executive_services(self):
        es = ExecutiveServices.from_dict(
            {
                "apps": [
                    {
                        "name": "HelloApp",
                        "class": "test_usecase.apps.hello_app.HelloApp",
                        "enabled": False,
                    }
                ]
            }
        )

        self.assertFalse(es._nodes[0].enabled)

    def test_duplicate_app_names_raise_clear_error(self):
        raw = {
            "apps": [
                {"name": "HelloApp", "class": "test_usecase.apps.hello_app.HelloApp"},
                {"name": "HelloApp", "class": "test_usecase.apps.hello_app.HelloApp"},
            ]
        }

        with self.assertLogs("fsw.config", level="ERROR"):
            config = parse_system_config(raw)

        self.assertIsNone(config["apps"][0]["fault"])
        self.assertIn("Duplicate app name", config["apps"][1]["fault"])

    def test_enabled_type_fault_disables_only_that_app(self):
        raw = {
            "apps": [
                {
                    "name": "HelloApp",
                    "class": "test_usecase.apps.hello_app.HelloApp",
                    "enabled": "false",
                }
            ]
        }

        with self.assertLogs("fsw.config", level="ERROR"):
            config = parse_system_config(raw)

        self.assertFalse(config["apps"][0]["enabled"])
        self.assertIn("must be true or false", config["apps"][0]["fault"])

    def test_invalid_logging_level_raises_clear_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown logging level"):
            configure_logging({"level": "LOUD"})

        logging.getLogger(__name__).addHandler(logging.NullHandler())

    def test_unused_system_keys_warn(self):
        raw = {
            "unused": True,
            "bus": {"maxsize": 10, "extra": 1},
            "logging": {"level": "INFO", "extra": 1},
            "apps": [
                {
                    "name": "HelloApp",
                    "class": "test_usecase.apps.hello_app.HelloApp",
                    "extra": 1,
                }
            ],
        }

        with self.assertLogs("fsw.config", level="WARNING") as logs:
            parse_system_config(raw)

        output = "\n".join(logs.output)
        self.assertIn("Unused key in system config ignored: unused", output)
        self.assertIn("Unused key in bus config ignored: extra", output)
        self.assertIn("Unused key in logging config ignored: extra", output)
        self.assertIn("Unused key in app entry HelloApp ignored: extra", output)

    def test_missing_app_config_file_becomes_app_fault(self):
        raw = {
            "apps": [
                {
                    "name": "HelloApp",
                    "class": "test_usecase.apps.hello_app.HelloApp",
                    "config": "missing.yml",
                }
            ]
        }

        with self.assertLogs("fsw.config", level="ERROR"):
            config = parse_system_config(raw, root="test_usecase/config")

        self.assertFalse(config["apps"][0]["enabled"])
        self.assertIn("missing.yml", config["apps"][0]["fault"])

    def test_load_env_reads_simple_key_values(self):
        values = load_env(".env")

        self.assertEqual(values["FSW_CONFIG_PATH"], "test_usecase/config/system.yml")
        self.assertEqual(values["FSW_LOG_LEVEL"], "INFO")


if __name__ == "__main__":
    unittest.main()
