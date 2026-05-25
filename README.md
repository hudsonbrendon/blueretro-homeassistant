<p align="center">
  <img src="custom_components/blueretro/brand/logo.png" alt="BlueRetro" width="360">
</p>

# BlueRetro for Home Assistant

[![Tests](https://github.com/hudsonbrendon/blueretro-homeassistant/actions/workflows/test.yml/badge.svg)](https://github.com/hudsonbrendon/blueretro-homeassistant/actions/workflows/test.yml)
[![Validate](https://github.com/hudsonbrendon/blueretro-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/hudsonbrendon/blueretro-homeassistant/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/hudsonbrendon/blueretro-homeassistant)](https://github.com/hudsonbrendon/blueretro-homeassistant/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Autodiscovers a [BlueRetro](https://github.com/darthcloud/BlueRetro) adapter over Bluetooth
and exposes read-only sensors plus reboot/deep-sleep controls.

## Limits

- Works only while the adapter is **idle** (no controller connected). During gameplay the
  config BLE is unavailable, so entities show `unavailable` — by design, to protect gameplay.
- No battery or live controller input (the hardware does not expose them).

## Install

1. Add this repo as a HACS custom repository (category: Integration).
2. Install **BlueRetro** and restart Home Assistant.
3. Power the BlueRetro with no controller connected; Home Assistant discovers it automatically.

## Entities

- Sensors: Firmware, Game ID, Game, Config source, ABI version (diag), BD address (diag).
- Binary sensor: Config available (connectivity).
- Buttons: Reboot, Deep sleep.
