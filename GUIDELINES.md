# Barebones Coding Guidelines

These guidelines keep the framework small, readable, and consistent.

## Code Style

- Prefer plain Python over clever abstractions.
- Keep each file focused on one idea.
- Use descriptive names such as `SoftwareBus`, `Message`, `PublisherApp`, and `SubscriberApp`.
- Use type hints where they make inputs, outputs, or stored attributes clearer.
- Avoid hidden behavior. Lifecycle order should be obvious: `init()` -> `run()` -> `shutdown()`.
- Use only the Python standard library.

## Comments

- Comments should explain intent, not repeat the code.
- Add comments only for lifecycle boundaries, thread behavior, or non-obvious choices.
- If code is already clear, do not add a comment.

## Logging

- Framework files use `logging.getLogger(__name__)`.
- App files use `logging.getLogger(self.name)`.
- Use `INFO` for lifecycle events and received values.
- Use `DEBUG` for repeated publisher messages.
- Use `WARNING` for dropped messages.

## Tests

- Use standard-library `unittest`.
- Keep tests small.
- Test one behavior per test method.
- Prefer simple test helper classes over mocks when possible.

## Configuration

- Keep YAML files simple: plain keys, simple values, and short lists.
- Use `.env` only for small runtime constants such as config path and log level.
- Put system-level settings in `test_usecase/config/system.yml`.
- Put app-specific settings in one small YAML file per app.
- Use `enabled` to turn an app on or off.
- Use lower `priority` numbers to start apps earlier.
- App `config` can be either a YAML file path or a small inline mapping.
- Each app should load config through a small frozen dataclass.
- Unknown config keys should warn; wrong config value types should fail fast.
- Keep scheduling, filtering, control logic, and other mission behavior in apps unless it is truly generic framework behavior.

## Comms

- Keep reusable transport code in `fsw/apps`.
- Keep mission-specific command handling in the usecase apps.
- UDP comms payloads are plain text for now.
- Do not add packet formats, encryption, sessions, or routing until the simple path needs it.

## Fault Tolerance

- One app fault should not stop unrelated apps.
- Failed app config should be reported and skipped.
- Failed app startup should be reported and skipped.
- Run-loop crashes should be captured in app health.
- Keep recovery simple: stop and restart individual nodes by name.
- Watchdogs should stay simple: one watched topic, one timeout, one alert topic.
- Repeating fault events should go through `EventServices` rate limiting.
