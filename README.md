<p align="center">
  <img src="custom_components/blueretro/brand/logo.png" alt="BlueRetro" width="420">
</p>

# BlueRetro for Home Assistant

[![Tests](https://github.com/hudsonbrendon/blueretro-homeassistant/actions/workflows/test.yml/badge.svg)](https://github.com/hudsonbrendon/blueretro-homeassistant/actions/workflows/test.yml)
[![Validate](https://github.com/hudsonbrendon/blueretro-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/hudsonbrendon/blueretro-homeassistant/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/hudsonbrendon/blueretro-homeassistant)](https://github.com/hudsonbrendon/blueretro-homeassistant/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Auto-discovers a **[BlueRetro](https://github.com/darthcloud/BlueRetro)**
retro-console Bluetooth adapter over Bluetooth and exposes its status, current
game, and configuration in Home Assistant — read-only sensors, mode/accessory
selects, and reboot/deep-sleep buttons.

The Bluetooth protocol and device control live in a separate Python library,
[**`blueretro-ble`**](https://github.com/hudsonbrendon/blueretro-ble)
([PyPI](https://pypi.org/project/blueretro-ble/)), which this integration pulls in
automatically via `manifest.json` `requirements`.

## Features

- 🔍 **Automatic discovery** — power the BlueRetro near Home Assistant with no
  controller connected and it shows up as a discovered device (no MAC address or
  YAML required).
- 📊 **Sensors** — Firmware, Game ID, Game, Config source, plus diagnostics: ABI
  version, BD address, pairing mode, multitap, memory-card bank and firmware name.
- 🟢 **Config available** — a connectivity `binary_sensor`, on while the adapter is
  idle and reachable.
- 🎛️ **Selects** — Controller mode (GamePad / GamePadAlt / Keyboard / Mouse) and
  Accessory (None / Memory / Rumble / Both) **per output port** (multitap), plus
  Memory card bank, Multitap, System and Pairing mode (global config).
- 🔁 **Buttons** — Reboot, Deep sleep and Factory reset.
- ⬆️ **Firmware update** — an `update` entity that flags when a newer
  `darthcloud/BlueRetro` release exists and links to it (detection only; no OTA).
- ⏱️ **Configurable** — tune the poll interval (1–60 minutes) and the number of
  output ports to expose (1–12, for multitap) from the integration's options.
- 🌍 **Translations** — English, Portuguese (BR and PT) and Spanish.
- 📡 **Works through ESPHome Bluetooth proxies** — uses Home Assistant's shared
  Bluetooth stack, so the adapter only needs to be near a proxy, not the HA host.

## Requirements

- Home Assistant **2024.12** or newer.
- A Bluetooth adapter on the Home Assistant host **or** an
  [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html)
  within range of the adapter.
- A BlueRetro adapter, **idle** (no controller connected — the configuration
  interface is only reachable then).

## Installation

### HACS (recommended)

1. In Home Assistant, open **HACS → ⋮ (top right) → Custom repositories**.
2. Add the repository URL `https://github.com/hudsonbrendon/blueretro-homeassistant`
   and choose the **Integration** category.
3. Search for **BlueRetro** in HACS, install it, and **restart Home Assistant**.

### Manual

1. Copy `custom_components/blueretro/` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

## Setup

1. Power on the BlueRetro **with no controller connected**, within range of Home
   Assistant (or a Bluetooth proxy).
2. Home Assistant discovers it automatically — go to **Settings → Devices &
   Services** and confirm the discovered **BlueRetro** device.
3. If it isn't auto-discovered, add it manually: **Settings → Devices & Services →
   Add Integration → BlueRetro**, then pick the adapter from the list.

## Entities

| Type | Entity | Notes |
|---|---|---|
| `sensor` | Firmware, Game ID, Game, Config source | primary |
| `sensor` | ABI version, BD address, Firmware name | diagnostic |
| `binary_sensor` | Config available | connectivity (on while idle/reachable) |
| `select` | Controller mode / Accessory (per port), Memory card bank, Multitap, System, Pairing mode | mode/accessory write the per-port output config; Memory card bank / Multitap / System / Pairing mode write the global config and reboot the adapter to apply |
| `button` | Reboot, Deep sleep, Factory reset | Factory reset restores original firmware/configuration |
| `update` | Firmware | flags a newer GitHub release; detection only (no OTA install) |

The integration's **Configure** (options) dialog tunes the poll interval (1–60
minutes, default 5) and the number of output ports to expose (1–12, default 1).
Raise the port count for multitap setups to get a Controller mode / Accessory
pair per port.

## Services

Target a BlueRetro device:

| Service | What it does |
|---|---|
| `blueretro.list_config_files` | List the per-GameID config files on the adapter (returns a response). |
| `blueretro.delete_config_file` | Delete a stored per-GameID config file by name. |
| `blueretro.get_input_mapping` | Read advanced input mappings for a config slot (returns a response). |
| `blueretro.set_input_mapping` | Write advanced input mappings (src/dest/dest_id/max/threshold/deadzone/turbo/scaling/diag_scaling) to a slot. |

> **Not exposed:** memory-card (VMU) and N64 Controller Pak backup/restore and
> OTA firmware install are implemented in `blueretro-ble` but need a high BLE MTU
> that Home Assistant's stack doesn't negotiate. Use the official
> [web config](https://blueretro.io) (Chrome, MTU 517) for those large transfers.

## How it works

This repository ships **only** the Home Assistant integration. All Bluetooth
work — discovery, connecting, decoding the config, and sending commands — lives
in the [`blueretro-ble`](https://github.com/hudsonbrendon/blueretro-ble) Python
library and is pulled in as a dependency.

## Limitations

- The adapter's configuration is only reachable while **idle** (no controller
  connected). During gameplay the entities show `unavailable` — by design, to
  avoid interfering with play.
- Bluetooth LE allows **one client at a time** — don't run the BlueRetro web
  config while Home Assistant is connected.
- **VMU (Dreamcast memory card) backup/restore is not provided** here: it needs a
  large BLE MTU and is unreliable over Home Assistant's Bluetooth stack. Use the
  official web config (in Chrome) for VMU backup/restore.
- **N64 Controller Pak backup/restore is not provided** here — like the Dreamcast
  VMU it needs a large BLE MTU and is unreliable over Home Assistant's Bluetooth
  stack. Use the official web config (in Chrome). The integration does let you pick
  the active **Memory Card Bank** (1–4) for N64.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Protocol/decoding changes belong in the
[`blueretro-ble`](https://github.com/hudsonbrendon/blueretro-ble) library, not here.

## License

[MIT](LICENSE) © Hudson Brendon
