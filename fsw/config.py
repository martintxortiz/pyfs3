import importlib
import logging
import os
from pathlib import Path
from typing import Any

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"


def load_system_config(path: str) -> dict[str, Any]:
    raw = load_yaml(path)
    return parse_system_config(raw, root=Path(path).parent)


def parse_system_config(raw: dict[str, Any], root: str | Path = ".") -> dict[str, Any]:
    _require_dict(raw, "system config")
    _warn_unknown_keys(raw, {"logging", "bus", "apps"}, "system config")
    bus_config = _require_dict(raw.get("bus", {}), "bus")
    logging_config = _require_dict(raw.get("logging", {}), "logging")
    _warn_unknown_keys(bus_config, {"maxsize"}, "bus config")
    _warn_unknown_keys(logging_config, {"level"}, "logging config")

    raw_apps = raw.get("apps", [])
    if not isinstance(raw_apps, list):
        raise ValueError("'apps' must be a list")

    app_names: set[str] = set()
    apps = [_parse_app_config(app, Path(root), app_names) for app in raw_apps]

    return {
        "bus_maxsize": _positive_int(bus_config.get("maxsize", 100), "bus.maxsize"),
        "logging": {"level": str(logging_config.get("level", "INFO"))},
        "apps": apps,
    }


def configure_logging(config: dict[str, Any]) -> None:
    level_name = str(config.get("level", "INFO")).upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        raise ValueError(f"Unknown logging level: {level_name}")

    logging.basicConfig(level=level, format=LOG_FORMAT)


def load_env(path: str | Path = ".env") -> dict[str, str]:
    env_path = Path(path)
    values: dict[str, str] = {}

    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                logging.getLogger(__name__).warning("Invalid .env line ignored: %s", line)
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")

    # Real environment overrides .env for FSW_* keys.
    values.update({k: v for k, v in os.environ.items() if k.startswith("FSW_")})
    return values


def load_yaml(path: str | Path) -> dict[str, Any]:
    lines = _clean_lines(Path(path).read_text(encoding="utf-8").splitlines())
    if not lines:
        return {}

    data, index = _parse_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise ValueError(f"Could not parse YAML near: {lines[index][1]}")
    if not isinstance(data, dict):
        raise ValueError("Top-level YAML value must be a mapping")
    return data


def _parse_app_config(
    app: dict[str, Any],
    root: Path,
    app_names: set[str],
) -> dict[str, Any]:
    name = app.get("name", "<invalid app>") if isinstance(app, dict) else "<invalid app>"

    try:
        _check_app(app)
        _warn_unknown_keys(
            app,
            {"name", "class", "enabled", "priority", "config"},
            f"app entry {app['name']}",
        )
        if app["name"] in app_names:
            raise ValueError(f"Duplicate app name: {app['name']}")
        app_names.add(app["name"])

        return {
            "name": app["name"],
            "class": _load_class(app["class"]),
            "enabled": _bool(app.get("enabled", True), f"{app['name']}.enabled"),
            "priority": int(app.get("priority", 100)),
            "config": _load_app_config(app.get("config", {}), root),
            "fault": None,
        }
    except Exception as error:
        logging.getLogger(__name__).error("App config fault for %s: %s", name, error)
        return {
            "name": str(name),
            "class": None,
            "enabled": False,
            "priority": 1000,
            "config": {},
            "fault": str(error),
        }


def _check_app(app: dict[str, Any]) -> None:
    _require_dict(app, "app entry")
    for key in ("name", "class"):
        if key not in app:
            raise ValueError(f"App entry is missing '{key}'")
        if not isinstance(app[key], str):
            raise ValueError(f"App '{key}' must be a string")


def _load_app_config(value: Any, root: Path) -> dict[str, Any]:
    if isinstance(value, str):
        return load_yaml(root / value)
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    raise ValueError("App 'config' must be a YAML file path or mapping")


def _load_class(class_path: str):
    module_name, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _positive_int(value: Any, name: str) -> int:
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return result


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false")
    return value


def _warn_unknown_keys(data: dict[str, Any], expected_keys: set[str], name: str) -> None:
    for key in sorted(data.keys() - expected_keys):
        logging.getLogger(__name__).warning("Unused key in %s ignored: %s", name, key)


def _clean_lines(raw_lines: list[str]) -> list[tuple[int, str]]:
    lines = []
    for raw in raw_lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        text = raw.split(" #", 1)[0].rstrip()
        lines.append((len(text) - len(text.lstrip(" ")), text.strip()))
    return lines


def _parse_block(lines: list[tuple[int, str]], index: int, indent: int):
    if lines[index][1].startswith("- "):
        return _parse_list(lines, index, indent)
    return _parse_dict(lines, index, indent)


def _parse_dict(lines: list[tuple[int, str]], index: int, indent: int):
    data = {}
    while index < len(lines):
        line_indent, text = lines[index]
        if line_indent < indent or text.startswith("- "):
            break
        if line_indent != indent:
            raise ValueError(f"Unexpected indentation near: {text}")

        key, value = _split_key_value(text)
        index += 1
        if value == "":
            if index >= len(lines) or lines[index][0] <= line_indent:
                data[key] = {}
            else:
                data[key], index = _parse_block(lines, index, lines[index][0])
        else:
            data[key] = _parse_scalar(value)

    return data, index


def _parse_list(lines: list[tuple[int, str]], index: int, indent: int):
    items: list[Any] = []
    while index < len(lines):
        line_indent, text = lines[index]
        if line_indent < indent or not text.startswith("- "):
            break
        if line_indent != indent:
            raise ValueError(f"Unexpected indentation near: {text}")

        item_text = text[2:].strip()
        index += 1

        if ":" not in item_text:
            items.append(_parse_scalar(item_text))
            continue

        key, value = _split_key_value(item_text)
        item: dict[str, Any] = {key: _parse_scalar(value)} if value else {}
        if value == "" and index < len(lines) and lines[index][0] > line_indent:
            item[key], index = _parse_block(lines, index, lines[index][0])
        if index < len(lines) and lines[index][0] > line_indent:
            extra, index = _parse_dict(lines, index, lines[index][0])
            item.update(extra)
        items.append(item)

    return items, index


def _split_key_value(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ValueError(f"Expected key/value pair near: {text}")
    key, value = text.split(":", 1)
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> Any:
    keywords = {"true": True, "false": False, "null": None}
    if value.lower() in keywords:
        return keywords[value.lower()]
    if value.startswith(("'", '"')) and value.endswith(("'", '"')):
        return value[1:-1]

    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            continue
    return value
