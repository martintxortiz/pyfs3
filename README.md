# pyfs3

This is a small, cFS-inspired Python framework for message-driven simulation apps.
It keeps framework code generic and puts mission/app behavior in apps.

## Run

```powershell
python main.py
```

The default runtime constants are in `.env`:

```env
FSW_CONFIG_PATH=test_usecase/config/system.yml
FSW_LOG_LEVEL=INFO
```

## Project Layout

- `fsw/` - reusable framework
- `fsw/apps/` - small reusable framework apps
- `test_usecase/apps/` - example apps
- `test_comms/` - flight-side comms example
- `test_ground_station/` - ground-side comms example
- `test_usecase/config/` - example YAML configs
- `tests/` - unit tests
- `GUIDELINES.md` - project style rules

## System Config

System config controls framework-level wiring:

```yaml
logging:
  level: INFO

bus:
  maxsize: 100

apps:
  - name: HelloApp
    class: test_usecase.apps.hello_app.HelloApp
    enabled: true
    priority: 30
    config: hello_app.yml
```

Rules:

- `enabled: false` disables an app.
- Lower `priority` starts earlier.
- `config` can be a YAML file path or an inline mapping.
- Unknown system/app-entry keys log warnings.
- Wrong value types raise errors.
- A broken app config disables only that app and is reported in health.

## App Config

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

## Fault Tolerance

The framework keeps failures local to the app when possible:

- If one app cannot load from config, ES records the fault and keeps the other apps usable.
- If one app fails during `init()`, startup continues for the remaining apps.
- If one app crashes inside `run()`, the crash is logged and the process keeps running.
- `stop_node(name)` and `restart_node(name)` can manage one app without stopping ES.

Inspect state with:

```python
health = es.health()
```

Each app reports:

- `enabled`
- `priority`
- `state`
- `error`

## UDP Comms Example

Two usecases prove simple uplink/downlink over UDP:

- `test_comms` listens on port `5100` and sends to `5200`.
- `test_ground_station` listens on port `5200` and sends to `5100`.

Run them in two terminals by setting `FSW_CONFIG_PATH` before `python main.py`.

Flight side:

```powershell
$env:FSW_CONFIG_PATH="test_comms/config/system.yml"
python main.py
```

Ground side:

```powershell
$env:FSW_CONFIG_PATH="test_ground_station/config/system.yml"
python main.py
```

Anything typed in one terminal is sent to the other side. From ground, type:

```text
sensor/get_value
```

The flight-side `SensorApp` replies with:

```text
sensor/value 42.00
```

Reusable framework apps:

- `CommandIngestApp` receives UDP text and publishes it to the bus.
- `TelemetryOutputApp` subscribes to bus text and sends it over UDP.
- `TerminalBridgeApp` sends terminal input and prints received messages.
- `WatchdogApp` publishes an alert when a heartbeat topic goes quiet.

Watchdog config example:

```yaml
heartbeat_topic: heartbeat/ground_link
timeout_seconds: 10.0
alert_topic: telemetry/out
alert_message: GROUND_LINK_TIMEOUT
alert_min_interval_seconds: 10.0
poll_seconds: 0.2
```

`alert_min_interval_seconds` is the event rate limit. If the link stays down,
the watchdog keeps checking but only sends one alert per configured interval.

## Add An App

1. Create a new file under `test_usecase/apps/`.
2. Subclass `Node`.
3. Define a config dataclass if the app needs settings.
4. Add the app to `test_usecase/config/system.yml`.

The framework does not need to change.

## Test

```powershell
python -m unittest discover -s tests
```
