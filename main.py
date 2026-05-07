import time

from fsw import ExecutiveServices, configure_logging, load_env, load_system_config

CONFIG_PATH = "examples/hello.yml"
ENV_PATH = ".env"


def main() -> None:
    env = load_env(ENV_PATH)

    try:
        config = load_system_config(env.get("FSW_CONFIG_PATH", CONFIG_PATH))
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
