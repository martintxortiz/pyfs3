import logging
import os
import tempfile
import unittest
from pathlib import Path

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


class YamlScalarTests(unittest.TestCase):
    """The YAML parser is custom; cover scalar coercion in one place."""

    def test_load_yaml_parses_bool_null_quoted_and_numeric_scalars(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scalars.yml"
            path.write_text(
                "yes_flag: true\n"
                "no_flag: false\n"
                "absent: null\n"
                "count: 42\n"
                "ratio: 3.14\n"
                "single: 'hello'\n"
                "double: \"world\"\n",
                encoding="utf-8",
            )
            data = load_yaml(path)

        self.assertEqual(data["yes_flag"], True)
        self.assertEqual(data["no_flag"], False)
        self.assertIsNone(data["absent"])
        self.assertEqual(data["count"], 42)
        self.assertIsInstance(data["count"], int)
        self.assertEqual(data["ratio"], 3.14)
        self.assertIsInstance(data["ratio"], float)
        self.assertEqual(data["single"], "hello")
        self.assertEqual(data["double"], "world")

    def test_load_yaml_strips_inline_comments_and_blank_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "comments.yml"
            path.write_text(
                "# top comment\n"
                "\n"
                "name: rover # trailing comment\n"
                "  \n"
                "count: 7\n",
                encoding="utf-8",
            )
            data = load_yaml(path)

        self.assertEqual(data, {"name": "rover", "count": 7})

    def test_load_yaml_rejects_top_level_non_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "list.yml"
            path.write_text("- one\n- two\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Top-level YAML value must be a mapping"):
                load_yaml(path)

    def test_load_yaml_rejects_inconsistent_indentation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yml"
            path.write_text("a: 1\n  b: 2\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unexpected indentation"):
                load_yaml(path)


class SystemConfigErrorTests(unittest.TestCase):
    def test_apps_must_be_a_list(self):
        with self.assertRaisesRegex(ValueError, "'apps' must be a list"):
            parse_system_config({"apps": {"name": "X"}})

    def test_zero_bus_maxsize_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "bus.maxsize must be greater than 0"):
            parse_system_config({"bus": {"maxsize": 0}, "apps": []})

    def test_negative_bus_maxsize_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "bus.maxsize must be greater than 0"):
            parse_system_config({"bus": {"maxsize": -5}, "apps": []})

    def test_top_level_must_be_a_mapping(self):
        with self.assertRaisesRegex(ValueError, "system config must be a mapping"):
            parse_system_config([])  # type: ignore[arg-type]

    def test_app_missing_class_key_becomes_app_fault(self):
        raw = {"apps": [{"name": "Orphan"}]}

        with self.assertLogs("fsw.config", level="ERROR"):
            config = parse_system_config(raw)

        self.assertFalse(config["apps"][0]["enabled"])
        self.assertIn("missing 'class'", config["apps"][0]["fault"])

    def test_app_missing_name_key_becomes_app_fault(self):
        raw = {"apps": [{"class": "test_usecase.apps.hello_app.HelloApp"}]}

        with self.assertLogs("fsw.config", level="ERROR"):
            config = parse_system_config(raw)

        self.assertFalse(config["apps"][0]["enabled"])
        self.assertIn("missing 'name'", config["apps"][0]["fault"])
        # Without a usable name the framework must fall back to a placeholder, not crash.
        self.assertEqual(config["apps"][0]["name"], "<invalid app>")

    def test_app_config_with_unsupported_type_becomes_app_fault(self):
        raw = {
            "apps": [
                {
                    "name": "HelloApp",
                    "class": "test_usecase.apps.hello_app.HelloApp",
                    "config": 42,
                }
            ]
        }

        with self.assertLogs("fsw.config", level="ERROR"):
            config = parse_system_config(raw)

        self.assertFalse(config["apps"][0]["enabled"])
        self.assertIn("YAML file path or mapping", config["apps"][0]["fault"])

    def test_app_class_path_that_does_not_exist_becomes_fault(self):
        raw = {
            "apps": [
                {
                    "name": "Bad",
                    "class": "fsw.does_not_exist.Nope",
                }
            ]
        }

        with self.assertLogs("fsw.config", level="ERROR"):
            config = parse_system_config(raw)

        self.assertFalse(config["apps"][0]["enabled"])
        self.assertIn("fsw.does_not_exist", config["apps"][0]["fault"])


class LoadEnvTests(unittest.TestCase):
    def test_returns_empty_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_env(Path(tmp) / "missing.env"), {})

    def test_strips_surrounding_quotes_from_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("SINGLE='one'\nDOUBLE=\"two\"\nBARE=three\n", encoding="utf-8")
            values = load_env(path)

        self.assertEqual(values["SINGLE"], "one")
        self.assertEqual(values["DOUBLE"], "two")
        self.assertEqual(values["BARE"], "three")

    def test_ignores_comments_and_blank_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("# comment\n\nKEY=value\n", encoding="utf-8")
            values = load_env(path)

        self.assertEqual(values, {"KEY": "value"})

    def test_warns_on_lines_without_equal_sign(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("VALID=ok\nnot_a_pair\n", encoding="utf-8")

            with self.assertLogs("fsw.config", level="WARNING") as logs:
                values = load_env(path)

        self.assertEqual(values["VALID"], "ok")
        self.assertNotIn("not_a_pair", values)
        self.assertIn("not_a_pair", "\n".join(logs.output))

    def test_real_environment_fsw_vars_override_file(self):
        marker = "FSW_TEST_OVERRIDE_MARKER"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(f"{marker}=from_file\n", encoding="utf-8")
            os.environ[marker] = "from_env"
            try:
                values = load_env(path)
            finally:
                del os.environ[marker]

        self.assertEqual(values[marker], "from_env")


if __name__ == "__main__":
    unittest.main()
