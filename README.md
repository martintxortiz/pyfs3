# pyfs3

A small, cFS-inspired Python framework for message-driven simulation apps.
Framework code stays generic; mission/app behavior lives in apps.

## Run

Pass an example name as a positional argument:

```powershell
python main.py            # default (hello)
python main.py hello
python main.py flight
python main.py ground
python main.py path/to/custom.yml
```

A bare name like `flight` resolves to `examples/flight.yml`. A literal path
is used as-is. With no argument, `FSW_CONFIG_PATH` from `.env` is used,
falling back to `examples/hello.yml`.

```env
FSW_CONFIG_PATH=examples/hello.yml
FSW_LOG_LEVEL=INFO
```

## Project layout

- `fsw/` - reusable framework
- `fsw/apps/` - small reusable framework apps (CommandIngest, TelemetryOutput, TerminalBridge, Watchdog)
- `examples/apps/` - example app code (HelloApp, SensorPublisherApp, PeriodicSenderApp, CommandHandlerApp)
- `examples/*.yml` - example system configs (`hello.yml`, `flight.yml`, `ground.yml`)
- `tests/` - unit tests
- `tests/fixtures/` - test fixtures
- `GUIDELINES.md` - project style rules

## System config

```yaml
logging:
  level: INFO

bus:
  maxsize: 100

apps:
  - name: HelloApp
    class: examples.apps.hello_app.HelloApp
    enabled: true
    priority: 30
    config:
      message: hi
      interval_seconds: 1.0
```

Rules:

- `enabled: false` disables an app.
- Lower `priority` starts earlier.
- `config` can be a YAML file path or an inline mapping.
- Unknown system/app-entry keys log warnings.
- Wrong value types raise errors.
- A broken app config disables only that app and is reported in health.

## App config

Each app owns its own config shape using a small dataclass:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class HelloConfig:
    message: str = "hello"
    interval_seconds: float = 1.0
```

Load it in `init()`:

```python
self.settings = self.load_config(HelloConfig)
```

This gives:

- defaults from the dataclass
- warnings for unused app config keys
- errors for wrong types
- readable typed settings inside the app

## Fault tolerance

The framework keeps failures local to the app when possible:

- If one app cannot load from config, ES records the fault and keeps the other apps usable.
- If one app fails during `init()`, startup continues for the remaining apps.
- If one app crashes inside `run()`, the crash is logged and the process keeps running.
- `stop_node(name)` and `restart_node(name)` can manage one app without stopping ES.

Inspect state with:

```python
health = es.health()
```

Each app reports `enabled`, `priority`, `state`, `error`.

## Flight + ground example

`examples/flight.yml` and `examples/ground.yml` run a two-process demo over UDP.
Together they exercise CommandIngest, TelemetryOutput, EventServices, and Watchdog.

Flight side:

- `SensorPublisher` - publishes a random sensor value once per second over UDP.
- `CommandHandler` - replies to `ping` with `pong`, and forwards `heartbeat` onto
  the watchdog topic.
- `Watchdog` - alerts (rate-limited via EventServices) if heartbeats stop.

Ground side:

- `Pinger` - sends `ping` every 2 s.
- `Heartbeater` - sends `heartbeat` every 1 s.
- `TerminalBridge` - prints incoming telemetry and forwards typed input.

Run them in two terminals:

```powershell
# terminal 1 - flight
python main.py flight
```

```powershell
# terminal 2 - ground
python main.py ground
```

You should see the flight side logging incoming `ping`/`heartbeat`, and the
ground side printing `pong` and `sensor/value <number>` lines.

To verify the watchdog and EventServices, stop the ground process. After
`timeout_seconds` (default 5 s) the flight side logs
`GROUND_LINK_TIMEOUT` as a warning, rate-limited to one alert per
`alert_min_interval_seconds`.

## Add an app

1. Create a new file under `examples/apps/` (or your own package).
2. Subclass `Node`.
3. Define a config dataclass if the app needs settings.
4. Add the app to a system YAML.

The framework does not need to change.

## Test

```powershell
python -m unittest discover -s tests
```
