# Contributing

Thanks for helping improve the BlueRetro Home Assistant integration!

## Development setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
pytest
```

Requires Python 3.12+. This repo ships only the Home Assistant integration
(`custom_components/blueretro`); the BLE protocol lives in the
[`blueretro-ble`](https://github.com/hudsonbrendon/blueretro-ble) library (PyPI),
pulled in via `manifest.json` `requirements`.

## Guidelines

- Keep `pytest` green and add tests for new behavior. Integration tests use
  `pytest-homeassistant-custom-component`; the bluetooth stack is mocked in
  `tests/integration/conftest.py`.
- Protocol/decoding changes belong in the `blueretro-ble` library, not here.
- The adapter is only reachable while **idle** (no controller connected); entities
  go `unavailable` during gameplay by design.

## Releasing

1. Bump `version` in `custom_components/blueretro/manifest.json` and update `CHANGELOG.md`.
2. Tag and push: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`.
3. Create a GitHub release for the tag — HACS offers it as an update.
