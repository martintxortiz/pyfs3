import sys
import time
from pathlib import Path

from fsw import ExecutiveServices, configure_logging, load_env, load_system_config

CONFIG_PATH = "examples/hello.yml"
ENV_PATH = ".env"
EXAMPLES_DIR = "examples"


def resolve_config_path(arg: str) -> str:
    """Allow either a path or a short example name like ``flight``."""
    if Path(arg).exists():
        return arg
    short = Path(EXAMPLES_DIR) / f"{arg}.yml"
    if short.exists():
        return str(short)
    return arg  # let load_system_config raise a clear error


def main() -> None:
    env = load_env(ENV_PATH)

    # Precedence: positional CLI arg > FSW_CONFIG_PATH env > default.
    if len(sys.argv) > 1:
        config_path = resolve_config_path(sys.argv[1])
    else:
        config_path = env.get("FSW_CONFIG_PATH", CONFIG_PATH)

    try:
        config = load_system_config(config_path)
    except Exception as error:
        print(f"System config fault: {error}")
        return

    if "FSW_LOG_LEVEL" in env:
        config["logging"]["level"] = env["FSW_LOG_LEVEL"]
    configure_logging(config["logging"])

    es = ExecutiveServices.from_config_data(config)
    es.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutdown requested.")
    finally:
        es.stop()


if __name__ == "__main__":
    main()
