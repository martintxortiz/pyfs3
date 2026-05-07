import logging
from dataclasses import dataclass

from .config import load_system_config, parse_system_config
from .event_services import EventServices
from .node import Node, NodeState
from .software_bus import SoftwareBus

logger = logging.getLogger(__name__)


@dataclass
class RegisteredNode:
    node: Node
    priority: int = 100
    enabled: bool = True


class ExecutiveServices:
    """Owns the SoftwareBus and manages node lifecycle."""

    def __init__(self, bus_maxsize: int = 100):
        self.bus = SoftwareBus(maxsize=bus_maxsize)
        self.events = EventServices(self.bus)
        self._nodes: list[RegisteredNode] = []
        self._started_nodes: list[RegisteredNode] = []
        self._faults: dict[str, str] = {}

    @classmethod
    def from_config(cls, path: str):
        config = load_system_config(path)
        return cls.from_config_data(config)

    @classmethod
    def from_dict(cls, raw: dict):
        config = parse_system_config(raw)
        return cls.from_config_data(config)

    @classmethod
    def from_config_data(cls, config: dict):
        es = cls(bus_maxsize=config["bus_maxsize"])

        for app in config["apps"]:
            if app.get("fault"):
                es._faults[app["name"]] = app["fault"]
                logger.error("[%s] not registered: %s", app["name"], app["fault"])
                continue

            try:
                node = app["class"](
                    name=app["name"],
                    bus=es.bus,
                    config=app["config"],
                )
                es.register(
                    node,
                    priority=app["priority"],
                    enabled=app["enabled"],
                )
            except Exception as error:
                es._faults[app["name"]] = str(error)
                logger.exception("[%s] failed during registration", app["name"])

        return es

    def register(self, node: Node, priority: int = 100, enabled: bool = True) -> None:
        if self._find_or_none(node.name):
            raise ValueError(f"Node already registered: {node.name}")

        if node.events is None:
            node.events = self.events

        self._nodes.append(RegisteredNode(node=node, priority=priority, enabled=enabled))
        logger.info(
            "Registered node: %s priority=%s enabled=%s",
            node.name,
            priority,
            enabled,
        )

    def start(self) -> None:
        logger.info("ExecutiveServices: starting all nodes")
        self._started_nodes = []
        for entry in sorted(self._nodes, key=lambda item: item.priority):
            if entry.enabled:
                if entry.node._start():
                    self._started_nodes.append(entry)
                else:
                    self._faults[entry.node.name] = entry.node.last_error or "start failed"
            else:
                logger.info("[%s] disabled; not started", entry.node.name)

    def stop(self) -> None:
        logger.info("ExecutiveServices: stopping all nodes")
        for entry in reversed(self._started_nodes):
            entry.node._stop()
        self._started_nodes = []

    def stop_node(self, name: str) -> None:
        entry = self._find(name)
        entry.node._stop()
        if entry in self._started_nodes:
            self._started_nodes.remove(entry)

    def restart_node(self, name: str) -> None:
        entry = self._find(name)
        if not entry.enabled:
            logger.info("[%s] disabled; not restarted", name)
            return

        entry.node._stop()
        if entry.node._start():
            if entry not in self._started_nodes:
                self._started_nodes.append(entry)
        else:
            self._faults[name] = entry.node.last_error or "restart failed"

    def health(self) -> dict[str, dict[str, object]]:
        report = {
            name: {
                "enabled": False,
                "priority": None,
                "state": NodeState.FAILED.value,
                "error": error,
            }
            for name, error in self._faults.items()
        }

        for entry in self._nodes:
            report[entry.node.name] = {
                "enabled": entry.enabled,
                "priority": entry.priority,
                "state": entry.node.state.value,
                "error": entry.node.last_error,
            }

        return report

    def _find(self, name: str) -> RegisteredNode:
        entry = self._find_or_none(name)
        if entry:
            return entry
        raise KeyError(f"No node named {name}")

    def _find_or_none(self, name: str) -> RegisteredNode | None:
        for entry in self._nodes:
            if entry.node.name == name:
                return entry
        return None
