# BlueRetro Home Assistant Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure Python BLE library (`blueretro_ble`) plus a thin Home Assistant custom integration that autodiscovers a BlueRetro adapter over Bluetooth, exposes read-only sensors, and offers reboot/deep-sleep controls.

**Architecture:** A pure library talks to the BlueRetro GATT server via `bleak` + `bleak-retry-connector` (connect → read/write → disconnect). A thin `custom_components/blueretro` integration wires the library into HA: bluetooth discovery → config flow → `DataUpdateCoordinator` polling → sensor/binary_sensor/button entities. The device only accepts connections while idle (no controller connected), so failed connections during gameplay simply mark entities unavailable.

**Tech Stack:** Python 3.12+, `bleak`, `bleak-retry-connector`, Home Assistant `bluetooth` component, `pytest`, `pytest-asyncio`, `pytest-homeassistant-custom-component`, stdlib `sqlite3`.

**Confirmed BLE protocol** (from `darthcloud/BlueRetroWebCfg`):
- Service UUID: `56830f56-5180-fab0-314b-2fa176799a00`
- `...a06` direct read → ABI version (first byte int)
- `...a09` direct read → firmware/app version (UTF-8 string)
- `...a0c` direct read → BD address (6 bytes, reversed)
- `...a07` command char: write 1 command byte, then read response
  - `0x04` get game id (string), `0x05` get config source (first byte int)
  - `0x38` reboot, `0x37` deep sleep
- `gameid.db` is a SQLite file with table `games(id TEXT, name TEXT)`

---

## Task 1: Repository scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `blueretro_ble/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/lib/__init__.py`
- Create: `tests/lib/test_smoke.py`
- Create: `blueretro_ble/gameid.db` (downloaded binary)

- [ ] **Step 1: Create `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/
.coverage
dist/
build/
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "blueretro-ble"
version = "0.1.0"
description = "BLE library for the BlueRetro retro-console Bluetooth adapter"
requires-python = ">=3.12"
dependencies = [
    "bleak>=0.22.0",
    "bleak-retry-connector>=3.5.0",
]

[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-homeassistant-custom-component>=0.13",
]

[tool.setuptools]
packages = ["blueretro_ble"]

[tool.setuptools.package-data]
blueretro_ble = ["gameid.db"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Create empty package/test init files**

`blueretro_ble/__init__.py`:
```python
"""BlueRetro BLE library."""

__version__ = "0.1.0"
```

`tests/__init__.py`, `tests/lib/__init__.py`: empty files (zero bytes).

- [ ] **Step 4: Download the bundled game database**

Run:
```bash
gh api repos/darthcloud/BlueRetroWebCfg/contents/gameid.db --jq '.content' | base64 -d > blueretro_ble/gameid.db
```
Expected: creates `blueretro_ble/gameid.db` (~618 KB). Verify:
```bash
python -c "import sqlite3; c=sqlite3.connect('blueretro_ble/gameid.db'); print(c.execute(\"SELECT count(*) FROM games\").fetchone())"
```
Expected: prints a tuple with a positive count, e.g. `(12345,)`.

- [ ] **Step 5: Write the smoke test** in `tests/lib/test_smoke.py`

```python
def test_package_imports():
    import blueretro_ble

    assert blueretro_ble.__version__ == "0.1.0"
```

- [ ] **Step 6: Create venv, install, run the smoke test**

Run:
```bash
python -m venv .venv && . .venv/bin/activate && pip install -e ".[test]" && pytest tests/lib/test_smoke.py -v
```
Expected: PASS (1 passed).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore blueretro_ble tests
git commit -m "chore: scaffold blueretro_ble package and test harness"
```

---

## Task 2: Protocol constants

**Files:**
- Create: `blueretro_ble/const.py`
- Test: `tests/lib/test_const.py`

- [ ] **Step 1: Write the failing test** in `tests/lib/test_const.py`

```python
from blueretro_ble import const


def test_service_uuid():
    assert const.SERVICE_UUID == "56830f56-5180-fab0-314b-2fa176799a00"


def test_characteristic_uuids_share_service_prefix():
    prefix = "56830f56-5180-fab0-314b-2fa176799a"
    assert const.CHAR_ABI == prefix + "06"
    assert const.CHAR_CMD == prefix + "07"
    assert const.CHAR_APP == prefix + "09"
    assert const.CHAR_BDADDR == prefix + "0c"


def test_command_bytes():
    assert const.CMD_GET_GAMEID == 0x04
    assert const.CMD_GET_CFG_SRC == 0x05
    assert const.CMD_SYS_DEEP_SLEEP == 0x37
    assert const.CMD_SYS_RESET == 0x38
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/lib/test_const.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blueretro_ble.const'`.

- [ ] **Step 3: Write `blueretro_ble/const.py`**

```python
"""BlueRetro BLE protocol constants (from darthcloud/BlueRetroWebCfg)."""

SERVICE_UUID = "56830f56-5180-fab0-314b-2fa176799a00"

# Directly readable characteristics
CHAR_ABI = "56830f56-5180-fab0-314b-2fa176799a06"
CHAR_CMD = "56830f56-5180-fab0-314b-2fa176799a07"
CHAR_APP = "56830f56-5180-fab0-314b-2fa176799a09"
CHAR_BDADDR = "56830f56-5180-fab0-314b-2fa176799a0c"

# Command bytes written to CHAR_CMD, response read back from CHAR_CMD
CMD_GET_GAMEID = 0x04
CMD_GET_CFG_SRC = 0x05
CMD_SYS_DEEP_SLEEP = 0x37
CMD_SYS_RESET = 0x38

# Advertised BLE name prefix used for discovery
NAME_PREFIX = "BlueRetro"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/lib/test_const.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add blueretro_ble/const.py tests/lib/test_const.py
git commit -m "feat: add BlueRetro BLE protocol constants"
```

---

## Task 3: Byte parsers

**Files:**
- Create: `blueretro_ble/parser.py`
- Test: `tests/lib/test_parser.py`

- [ ] **Step 1: Write the failing test** in `tests/lib/test_parser.py`

```python
from blueretro_ble.parser import decode_abi, decode_bdaddr, decode_string


def test_decode_bdaddr_reverses_byte_order():
    raw = bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
    assert decode_bdaddr(raw) == "66:55:44:33:22:11"


def test_decode_bdaddr_pads_single_hex_digits():
    raw = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x0a])
    assert decode_bdaddr(raw) == "0a:05:04:03:02:01"


def test_decode_bdaddr_too_short_returns_none():
    assert decode_bdaddr(bytes([0x01, 0x02])) is None


def test_decode_string_utf8():
    assert decode_string(b"v1.8.1") == "v1.8.1"


def test_decode_string_strips_trailing_nulls():
    assert decode_string(b"abc\x00\x00") == "abc"


def test_decode_string_empty_returns_none():
    assert decode_string(b"") is None


def test_decode_abi_first_byte():
    assert decode_abi(bytes([0x02, 0x00])) == 2


def test_decode_abi_empty_returns_none():
    assert decode_abi(b"") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/lib/test_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blueretro_ble.parser'`.

- [ ] **Step 3: Write `blueretro_ble/parser.py`**

```python
"""Pure decoders for BlueRetro characteristic payloads."""

from __future__ import annotations


def decode_bdaddr(raw: bytes) -> str | None:
    """Decode a 6-byte BD address (little-endian, byte 5 first)."""
    if len(raw) < 6:
        return None
    return ":".join(f"{raw[i]:02x}" for i in range(5, -1, -1))


def decode_string(raw: bytes) -> str | None:
    """Decode a UTF-8 string, stripping trailing NULs. Empty -> None."""
    text = raw.decode("utf-8", errors="replace").rstrip("\x00").strip()
    return text or None


def decode_abi(raw: bytes) -> int | None:
    """Decode a small integer carried in the first byte."""
    if not raw:
        return None
    return raw[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/lib/test_parser.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add blueretro_ble/parser.py tests/lib/test_parser.py
git commit -m "feat: add byte parsers for BD address, strings, ABI"
```

---

## Task 4: Advertisement discovery predicate

**Files:**
- Create: `blueretro_ble/discovery.py`
- Test: `tests/lib/test_discovery.py`

The predicate is duck-typed: it accepts any object exposing `.name` (str | None) and
`.service_uuids` (list[str]). This matches HA's `BluetoothServiceInfoBleak`.

- [ ] **Step 1: Write the failing test** in `tests/lib/test_discovery.py`

```python
from dataclasses import dataclass, field

from blueretro_ble.const import SERVICE_UUID
from blueretro_ble.discovery import supports


@dataclass
class FakeInfo:
    name: str | None = None
    service_uuids: list[str] = field(default_factory=list)


def test_supports_name_and_service_uuid():
    info = FakeInfo(name="BlueRetro", service_uuids=[SERVICE_UUID])
    assert supports(info) is True


def test_supports_name_prefix_match():
    info = FakeInfo(name="BlueRetro_abcd", service_uuids=[SERVICE_UUID])
    assert supports(info) is True


def test_supports_name_only_still_true():
    # Some firmware advertises the name but not the service UUID.
    info = FakeInfo(name="BlueRetro_abcd", service_uuids=[])
    assert supports(info) is True


def test_supports_service_uuid_only_still_true():
    info = FakeInfo(name=None, service_uuids=[SERVICE_UUID])
    assert supports(info) is True


def test_supports_rejects_unrelated_device():
    info = FakeInfo(name="MyHeartRate", service_uuids=["0000180d-0000-1000-8000-00805f9b34fb"])
    assert supports(info) is False


def test_supports_rejects_empty():
    assert supports(FakeInfo()) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/lib/test_discovery.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blueretro_ble.discovery'`.

- [ ] **Step 3: Write `blueretro_ble/discovery.py`**

```python
"""Detect a BlueRetro device from its BLE advertisement."""

from __future__ import annotations

from typing import Protocol

from .const import NAME_PREFIX, SERVICE_UUID


class _AdvertisementLike(Protocol):
    name: str | None
    service_uuids: list[str]


def supports(info: _AdvertisementLike) -> bool:
    """True if the advertisement looks like a BlueRetro adapter."""
    name = info.name or ""
    if name.startswith(NAME_PREFIX):
        return True
    return SERVICE_UUID.lower() in {u.lower() for u in info.service_uuids}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/lib/test_discovery.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add blueretro_ble/discovery.py tests/lib/test_discovery.py
git commit -m "feat: add BlueRetro advertisement discovery predicate"
```

---

## Task 5: State model

**Files:**
- Create: `blueretro_ble/models.py`
- Test: `tests/lib/test_models.py`

- [ ] **Step 1: Write the failing test** in `tests/lib/test_models.py`

```python
from blueretro_ble.models import BlueRetroState


def test_default_state_is_unavailable_with_no_data():
    state = BlueRetroState()
    assert state.available is False
    assert state.fw_version is None
    assert state.abi_version is None
    assert state.bdaddr is None
    assert state.game_id is None
    assert state.game_name is None
    assert state.cfg_src is None


def test_state_accepts_values():
    state = BlueRetroState(
        available=True,
        fw_version="v1.8.1",
        abi_version=2,
        bdaddr="66:55:44:33:22:11",
        game_id="GALE01",
        game_name="Super Smash Bros. Melee",
        cfg_src=1,
    )
    assert state.available is True
    assert state.game_name == "Super Smash Bros. Melee"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/lib/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blueretro_ble.models'`.

- [ ] **Step 3: Write `blueretro_ble/models.py`**

```python
"""State container for a BlueRetro device."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BlueRetroState:
    """Snapshot of a BlueRetro adapter read over BLE."""

    available: bool = False
    fw_version: str | None = None
    abi_version: int | None = None
    bdaddr: str | None = None
    game_id: str | None = None
    game_name: str | None = None
    cfg_src: int | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/lib/test_models.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add blueretro_ble/models.py tests/lib/test_models.py
git commit -m "feat: add BlueRetroState model"
```

---

## Task 6: Game name lookup

**Files:**
- Create: `blueretro_ble/gameid.py`
- Test: `tests/lib/test_gameid.py`

- [ ] **Step 1: Write the failing test** in `tests/lib/test_gameid.py`

```python
import sqlite3

import pytest

from blueretro_ble.gameid import lookup_game_name


@pytest.fixture
def tiny_db(tmp_path):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE games (id TEXT, name TEXT)")
    conn.execute("INSERT INTO games VALUES ('GALE01', 'Super Smash Bros. Melee')")
    conn.commit()
    conn.close()
    return path


def test_lookup_returns_name(tiny_db):
    assert lookup_game_name("GALE01", db_path=tiny_db) == "Super Smash Bros. Melee"


def test_lookup_unknown_id_returns_none(tiny_db):
    assert lookup_game_name("NOPE99", db_path=tiny_db) is None


def test_lookup_none_id_returns_none(tiny_db):
    assert lookup_game_name(None, db_path=tiny_db) is None


def test_lookup_missing_db_returns_none(tmp_path):
    assert lookup_game_name("GALE01", db_path=tmp_path / "absent.db") is None


def test_lookup_uses_bundled_db_by_default():
    # Smoke check: a real ID present in the bundled DB resolves to a string.
    # GALE01 is Super Smash Bros. Melee (GameCube); adjust if absent.
    result = lookup_game_name("GALE01")
    assert result is None or isinstance(result, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/lib/test_gameid.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blueretro_ble.gameid'`.

- [ ] **Step 3: Write `blueretro_ble/gameid.py`**

```python
"""Resolve a BlueRetro Game ID to a human-readable game name."""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path


def _bundled_db_path() -> Path:
    return Path(str(resources.files("blueretro_ble") / "gameid.db"))


def lookup_game_name(game_id: str | None, db_path: Path | None = None) -> str | None:
    """Look up a game name in the SQLite game database.

    Returns None for unknown IDs, missing DB, or any read error.
    """
    if not game_id:
        return None
    path = db_path or _bundled_db_path()
    if not Path(path).exists():
        return None
    try:
        uri = f"file:{path}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            row = conn.execute(
                "SELECT name FROM games WHERE id = ? LIMIT 1", (game_id,)
            ).fetchone()
    except sqlite3.Error:
        return None
    return row[0] if row else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/lib/test_gameid.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add blueretro_ble/gameid.py tests/lib/test_gameid.py
git commit -m "feat: add game name lookup against bundled SQLite db"
```

---

## Task 7: Device read (`async_update`)

**Files:**
- Create: `blueretro_ble/device.py`
- Test: `tests/lib/test_device_update.py`

The device connects via `bleak_retry_connector.establish_connection`, reads three
characteristics directly, issues two command-then-read cycles on `CHAR_CMD`, resolves the
game name, and always disconnects.

- [ ] **Step 1: Write the failing test** in `tests/lib/test_device_update.py`

```python
from unittest.mock import AsyncMock, patch

import pytest

from blueretro_ble import const
from blueretro_ble.device import BlueRetroDevice


class FakeClient:
    """Minimal stand-in for a connected BleakClient."""

    def __init__(self):
        self._last_cmd = None
        self.disconnect = AsyncMock()
        self.is_connected = True

    async def read_gatt_char(self, uuid):
        if uuid == const.CHAR_ABI:
            return bytes([0x02])
        if uuid == const.CHAR_APP:
            return b"v1.8.1"
        if uuid == const.CHAR_BDADDR:
            return bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
        if uuid == const.CHAR_CMD:
            if self._last_cmd == const.CMD_GET_GAMEID:
                return b"GALE01"
            if self._last_cmd == const.CMD_GET_CFG_SRC:
                return bytes([0x01])
        raise AssertionError(f"unexpected read {uuid}")

    async def write_gatt_char(self, uuid, data, response=True):
        assert uuid == const.CHAR_CMD
        self._last_cmd = data[0]


@pytest.fixture
def fake_ble_device():
    dev = AsyncMock()
    dev.address = "AA:BB:CC:DD:EE:FF"
    dev.name = "BlueRetro_abcd"
    return dev


async def test_async_update_reads_all_fields(fake_ble_device):
    client = FakeClient()
    with (
        patch("blueretro_ble.device.establish_connection", AsyncMock(return_value=client)),
        patch("blueretro_ble.device.lookup_game_name", return_value="Super Smash Bros. Melee"),
    ):
        device = BlueRetroDevice()
        state = await device.async_update(fake_ble_device)

    assert state.available is True
    assert state.abi_version == 2
    assert state.fw_version == "v1.8.1"
    assert state.bdaddr == "66:55:44:33:22:11"
    assert state.game_id == "GALE01"
    assert state.cfg_src == 1
    assert state.game_name == "Super Smash Bros. Melee"
    client.disconnect.assert_awaited_once()


async def test_async_update_disconnects_even_on_read_error(fake_ble_device):
    client = FakeClient()
    client.read_gatt_char = AsyncMock(side_effect=Exception("boom"))
    with patch(
        "blueretro_ble.device.establish_connection", AsyncMock(return_value=client)
    ):
        device = BlueRetroDevice()
        state = await device.async_update(fake_ble_device)

    assert state.available is False
    client.disconnect.assert_awaited_once()


async def test_async_update_connection_failure_returns_unavailable(fake_ble_device):
    from bleak.exc import BleakError

    with patch(
        "blueretro_ble.device.establish_connection",
        AsyncMock(side_effect=BleakError("busy")),
    ):
        device = BlueRetroDevice()
        state = await device.async_update(fake_ble_device)

    assert state == device.last_state
    assert state.available is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/lib/test_device_update.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'blueretro_ble.device'`.

- [ ] **Step 3: Write `blueretro_ble/device.py`**

```python
"""High-level BlueRetro device operations over BLE."""

from __future__ import annotations

import logging

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from . import const
from .gameid import lookup_game_name
from .models import BlueRetroState
from .parser import decode_abi, decode_bdaddr, decode_string

_LOGGER = logging.getLogger(__name__)


class BlueRetroDevice:
    """Connects to a BlueRetro adapter to read state and send commands."""

    def __init__(self) -> None:
        self.last_state = BlueRetroState()

    async def _connect(self, ble_device: BLEDevice) -> BleakClient:
        return await establish_connection(
            BleakClient, ble_device, ble_device.address
        )

    async def async_update(self, ble_device: BLEDevice) -> BlueRetroState:
        """Connect, read all fields, disconnect. Never raises."""
        try:
            client = await self._connect(ble_device)
        except (BleakError, TimeoutError, OSError) as err:
            _LOGGER.debug("BlueRetro connect failed: %s", err)
            self.last_state = BlueRetroState(available=False)
            return self.last_state

        try:
            abi = decode_abi(await client.read_gatt_char(const.CHAR_ABI))
            fw = decode_string(await client.read_gatt_char(const.CHAR_APP))
            bdaddr = decode_bdaddr(await client.read_gatt_char(const.CHAR_BDADDR))
            game_id = decode_string(
                await self._command(client, const.CMD_GET_GAMEID)
            )
            cfg_src = decode_abi(
                await self._command(client, const.CMD_GET_CFG_SRC)
            )
        except (BleakError, TimeoutError, OSError, Exception) as err:  # noqa: BLE001
            _LOGGER.debug("BlueRetro read failed: %s", err)
            self.last_state = BlueRetroState(available=False)
            return self.last_state
        finally:
            await client.disconnect()

        state = BlueRetroState(
            available=True,
            fw_version=fw,
            abi_version=abi,
            bdaddr=bdaddr,
            game_id=game_id,
            cfg_src=cfg_src,
            game_name=lookup_game_name(game_id),
        )
        self.last_state = state
        return state

    async def _command(self, client: BleakClient, command: int) -> bytes:
        """Write a command byte to CHAR_CMD then read the response."""
        await client.write_gatt_char(const.CHAR_CMD, bytes([command]), response=True)
        return await client.read_gatt_char(const.CHAR_CMD)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/lib/test_device_update.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add blueretro_ble/device.py tests/lib/test_device_update.py
git commit -m "feat: add BlueRetroDevice.async_update read cycle"
```

---

## Task 8: Device commands (`async_reboot`, `async_deep_sleep`)

**Files:**
- Modify: `blueretro_ble/device.py`
- Test: `tests/lib/test_device_commands.py`

- [ ] **Step 1: Write the failing test** in `tests/lib/test_device_commands.py`

```python
from unittest.mock import AsyncMock, patch

import pytest

from blueretro_ble import const
from blueretro_ble.device import BlueRetroDevice


@pytest.fixture
def fake_ble_device():
    dev = AsyncMock()
    dev.address = "AA:BB:CC:DD:EE:FF"
    return dev


async def test_async_reboot_writes_reset_command(fake_ble_device):
    client = AsyncMock()
    with patch(
        "blueretro_ble.device.establish_connection", AsyncMock(return_value=client)
    ):
        await BlueRetroDevice().async_reboot(fake_ble_device)

    client.write_gatt_char.assert_awaited_once_with(
        const.CHAR_CMD, bytes([const.CMD_SYS_RESET]), response=True
    )
    client.disconnect.assert_awaited_once()


async def test_async_deep_sleep_writes_sleep_command(fake_ble_device):
    client = AsyncMock()
    with patch(
        "blueretro_ble.device.establish_connection", AsyncMock(return_value=client)
    ):
        await BlueRetroDevice().async_deep_sleep(fake_ble_device)

    client.write_gatt_char.assert_awaited_once_with(
        const.CHAR_CMD, bytes([const.CMD_SYS_DEEP_SLEEP]), response=True
    )
    client.disconnect.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/lib/test_device_commands.py -v`
Expected: FAIL with `AttributeError: 'BlueRetroDevice' object has no attribute 'async_reboot'`.

- [ ] **Step 3: Add command methods to `blueretro_ble/device.py`** (append inside the class, after `_command`)

```python
    async def async_reboot(self, ble_device: BLEDevice) -> None:
        """Reboot the adapter."""
        await self._send_command(ble_device, const.CMD_SYS_RESET)

    async def async_deep_sleep(self, ble_device: BLEDevice) -> None:
        """Put the adapter into deep sleep."""
        await self._send_command(ble_device, const.CMD_SYS_DEEP_SLEEP)

    async def _send_command(self, ble_device: BLEDevice, command: int) -> None:
        client = await self._connect(ble_device)
        try:
            await client.write_gatt_char(
                const.CHAR_CMD, bytes([command]), response=True
            )
        finally:
            await client.disconnect()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/lib/test_device_commands.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the whole library suite**

Run: `pytest tests/lib -v`
Expected: PASS (all library tests green).

- [ ] **Step 6: Commit**

```bash
git add blueretro_ble/device.py tests/lib/test_device_commands.py
git commit -m "feat: add reboot and deep-sleep commands"
```

---

## Task 9: Library public API

**Files:**
- Modify: `blueretro_ble/__init__.py`
- Test: `tests/lib/test_public_api.py`

- [ ] **Step 1: Write the failing test** in `tests/lib/test_public_api.py`

```python
def test_public_exports():
    from blueretro_ble import (
        BlueRetroDevice,
        BlueRetroState,
        SERVICE_UUID,
        supports,
    )

    assert SERVICE_UUID.endswith("a00")
    assert callable(supports)
    assert BlueRetroDevice is not None
    assert BlueRetroState is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/lib/test_public_api.py -v`
Expected: FAIL with `ImportError: cannot import name 'BlueRetroDevice'`.

- [ ] **Step 3: Rewrite `blueretro_ble/__init__.py`**

```python
"""BlueRetro BLE library."""

from .const import SERVICE_UUID
from .device import BlueRetroDevice
from .discovery import supports
from .models import BlueRetroState

__version__ = "0.1.0"

__all__ = [
    "SERVICE_UUID",
    "BlueRetroDevice",
    "BlueRetroState",
    "supports",
    "__version__",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/lib/test_public_api.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add blueretro_ble/__init__.py tests/lib/test_public_api.py
git commit -m "feat: expose blueretro_ble public API"
```

---

## Task 10: Integration scaffolding

**Files:**
- Create: `custom_components/blueretro/__init__.py`
- Create: `custom_components/blueretro/const.py`
- Create: `custom_components/blueretro/manifest.json`
- Create: `tests/integration/__init__.py`
- Create: `tests/conftest.py`
- Test: `tests/integration/test_manifest.py`

- [ ] **Step 1: Write the failing test** in `tests/integration/test_manifest.py`

```python
import json
from pathlib import Path


def test_manifest_is_valid():
    path = Path("custom_components/blueretro/manifest.json")
    data = json.loads(path.read_text())
    assert data["domain"] == "blueretro"
    assert data["config_flow"] is True
    assert data["iot_class"] == "local_polling"
    assert "bluetooth_adapters" in data["dependencies"]
    assert data["bluetooth"] == [{"local_name": "BlueRetro*"}]
    assert any(r.startswith("blueretro-ble") for r in data["requirements"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_manifest.py -v`
Expected: FAIL with `FileNotFoundError` for the manifest.

- [ ] **Step 3: Create `custom_components/blueretro/manifest.json`**

```json
{
  "domain": "blueretro",
  "name": "BlueRetro",
  "version": "0.1.0",
  "codeowners": [],
  "config_flow": true,
  "dependencies": ["bluetooth_adapters"],
  "documentation": "https://github.com/hudsonbrendon/blueretro-homeassistant",
  "integration_type": "device",
  "iot_class": "local_polling",
  "requirements": ["blueretro-ble==0.1.0"],
  "bluetooth": [{ "local_name": "BlueRetro*" }]
}
```

- [ ] **Step 4: Create `custom_components/blueretro/const.py`**

```python
"""Constants for the BlueRetro integration."""

from datetime import timedelta

DOMAIN = "blueretro"
SCAN_INTERVAL = timedelta(minutes=5)
```

- [ ] **Step 5: Create a minimal `custom_components/blueretro/__init__.py`**

```python
"""The BlueRetro integration."""

from __future__ import annotations
```

- [ ] **Step 6: Create `tests/integration/__init__.py`** (empty) and **`tests/conftest.py`**

`tests/conftest.py`:
```python
"""Shared fixtures enabling custom integrations in HA tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom_components/ in every HA test."""
    yield
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/integration/test_manifest.py -v`
Expected: PASS (1 passed).

- [ ] **Step 8: Commit**

```bash
git add custom_components/blueretro tests/integration tests/conftest.py
git commit -m "feat: scaffold blueretro custom integration"
```

---

## Task 11: Config flow (bluetooth + user)

**Files:**
- Create: `custom_components/blueretro/config_flow.py`
- Test: `tests/integration/test_config_flow.py`

- [ ] **Step 1: Write the failing test** in `tests/integration/test_config_flow.py`

```python
from unittest.mock import patch

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import SOURCE_BLUETOOTH
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import (
    generate_advertisement_data,
    generate_ble_device,
)

from blueretro_ble.const import SERVICE_UUID
from custom_components.blueretro.const import DOMAIN

ADDRESS = "AA:BB:CC:DD:EE:FF"


def _service_info(
    name: str = "BlueRetro_abcd", service_uuids: list[str] | None = None
) -> BluetoothServiceInfoBleak:
    """Build a BluetoothServiceInfoBleak using HA's version-stable helpers."""
    uuids = [SERVICE_UUID] if service_uuids is None else service_uuids
    device = generate_ble_device(ADDRESS, name)
    adv = generate_advertisement_data(local_name=name, service_uuids=uuids)
    return BluetoothServiceInfoBleak.from_advertisement(device, adv, "local")


async def test_bluetooth_discovery_creates_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=_service_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(
        "custom_components.blueretro.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "BlueRetro_abcd"
    assert result2["result"].unique_id == ADDRESS


async def test_bluetooth_discovery_rejects_non_blueretro(hass):
    info = _service_info(name="RandomThing", service_uuids=[])
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_config_flow.py -v`
Expected: FAIL with an error importing `config_flow` / no config flow registered.

- [ ] **Step 3: Write `custom_components/blueretro/config_flow.py`**

```python
"""Config flow for BlueRetro."""

from __future__ import annotations

from typing import Any

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
import voluptuous as vol

from blueretro_ble import supports

from .const import DOMAIN


class BlueRetroConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BlueRetro."""

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a discovery via the bluetooth integration."""
        if not supports(discovery_info):
            return self.async_abort(reason="not_supported")
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding a discovered device."""
        assert self._discovery is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery.name, data={}
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._discovery.name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the manual/user step listing discovered devices."""
        if user_input is not None:
            address = user_input["address"]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            info = self._discovered[address]
            return self.async_create_entry(title=info.name, data={})

        current = self._async_current_ids()
        for info in async_discovered_service_info(self.hass):
            if info.address in current or info.address in self._discovered:
                continue
            if supports(info):
                self._discovered[info.address] = info

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("address"): vol.In(
                        {a: i.name for a, i in self._discovered.items()}
                    )
                }
            ),
        )
```

- [ ] **Step 4: Add the `strings.json`** at `custom_components/blueretro/strings.json`

```json
{
  "config": {
    "flow_title": "{name}",
    "step": {
      "bluetooth_confirm": {
        "description": "Do you want to set up {name}?"
      },
      "user": {
        "data": { "address": "Device" }
      }
    },
    "abort": {
      "not_supported": "This device is not a BlueRetro adapter.",
      "no_devices_found": "No BlueRetro devices found.",
      "already_configured": "Device is already configured."
    }
  }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/integration/test_config_flow.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add custom_components/blueretro/config_flow.py custom_components/blueretro/strings.json tests/integration/test_config_flow.py
git commit -m "feat: add BlueRetro config flow (bluetooth + user)"
```

---

## Task 12: Coordinator and entry setup

**Files:**
- Create: `custom_components/blueretro/coordinator.py`
- Create: `custom_components/blueretro/entity.py`
- Modify: `custom_components/blueretro/__init__.py`
- Test: `tests/integration/test_init.py`

- [ ] **Step 1: Write the failing test** in `tests/integration/test_init.py`

```python
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from blueretro_ble import BlueRetroState
from custom_components.blueretro.const import DOMAIN


async def test_setup_and_unload_entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)

    state = BlueRetroState(available=True, fw_version="v1.8.1")
    with (
        patch(
            "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_update",
            AsyncMock(return_value=state),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_init.py -v`
Expected: FAIL — `async_setup_entry` not defined / coordinator import error.

- [ ] **Step 3: Write `custom_components/blueretro/coordinator.py`**

```python
"""Polling coordinator for a BlueRetro device."""

from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from blueretro_ble import BlueRetroDevice, BlueRetroState

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class BlueRetroCoordinator(DataUpdateCoordinator[BlueRetroState]):
    """Polls a BlueRetro adapter while it is idle/connectable."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL
        )
        self.address: str = entry.unique_id
        self.device = BlueRetroDevice()

    async def _async_update_data(self) -> BlueRetroState:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            return BlueRetroState(available=False)
        return await self.device.async_update(ble_device)

    def ble_device(self):
        """Return the current connectable BLEDevice or None."""
        return bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
```

- [ ] **Step 4: Write `custom_components/blueretro/entity.py`**

```python
"""Base entity for BlueRetro."""

from __future__ import annotations

from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BlueRetroCoordinator


class BlueRetroEntity(CoordinatorEntity[BlueRetroCoordinator]):
    """Shared device info and availability."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BlueRetroCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={("bluetooth", coordinator.address)},
            name="BlueRetro",
            manufacturer="darthcloud",
            model="BlueRetro",
            sw_version=coordinator.data.fw_version if coordinator.data else None,
        )

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.available
        )
```

- [ ] **Step 5: Rewrite `custom_components/blueretro/__init__.py`**

```python
"""The BlueRetro integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import BlueRetroCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

type BlueRetroConfigEntry = ConfigEntry[BlueRetroCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: BlueRetroConfigEntry
) -> bool:
    """Set up BlueRetro from a config entry."""
    coordinator = BlueRetroCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BlueRetroConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

Note: the three platform files are created in Tasks 13–15. Until then,
`async_forward_entry_setups` will warn about missing platforms. To keep this task's
test green, the platform modules are created as empty stubs now:

- [ ] **Step 6: Create no-op platform stubs** so `async_forward_entry_setups` succeeds

HA looks up `async_setup_entry` in each forwarded platform module; a docstring-only stub
would raise `AttributeError`. Each stub therefore defines a no-op `async_setup_entry`.
Tasks 13–15 replace these files entirely.

`custom_components/blueretro/sensor.py`:
```python
"""BlueRetro sensors (implemented in a later task)."""


async def async_setup_entry(hass, entry, async_add_entities):
    """Placeholder until the sensor platform is implemented."""
    return None
```
`custom_components/blueretro/binary_sensor.py`:
```python
"""BlueRetro binary sensors (implemented in a later task)."""


async def async_setup_entry(hass, entry, async_add_entities):
    """Placeholder until the binary_sensor platform is implemented."""
    return None
```
`custom_components/blueretro/button.py`:
```python
"""BlueRetro buttons (implemented in a later task)."""


async def async_setup_entry(hass, entry, async_add_entities):
    """Placeholder until the button platform is implemented."""
    return None
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/integration/test_init.py -v`
Expected: PASS (1 passed).

- [ ] **Step 8: Commit**

```bash
git add custom_components/blueretro tests/integration/test_init.py
git commit -m "feat: add coordinator, base entity, and entry setup"
```

---

## Task 13: Sensor platform

**Files:**
- Modify: `custom_components/blueretro/sensor.py`
- Test: `tests/integration/test_sensor.py`

- [ ] **Step 1: Write the failing test** in `tests/integration/test_sensor.py`

```python
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from blueretro_ble import BlueRetroState
from custom_components.blueretro.const import DOMAIN


async def _setup(hass, state):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_update",
            AsyncMock(return_value=state),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_sensors_report_values(hass):
    state = BlueRetroState(
        available=True,
        fw_version="v1.8.1",
        abi_version=2,
        bdaddr="66:55:44:33:22:11",
        game_id="GALE01",
        game_name="Super Smash Bros. Melee",
        cfg_src=1,
    )
    await _setup(hass, state)

    assert hass.states.get("sensor.blueretro_firmware").state == "v1.8.1"
    assert hass.states.get("sensor.blueretro_game_id").state == "GALE01"
    assert (
        hass.states.get("sensor.blueretro_game").state
        == "Super Smash Bros. Melee"
    )
    assert hass.states.get("sensor.blueretro_config_source").state == "1"
    assert hass.states.get("sensor.blueretro_abi_version").state == "2"
    assert (
        hass.states.get("sensor.blueretro_bd_address").state
        == "66:55:44:33:22:11"
    )


async def test_sensors_unavailable_when_offline(hass):
    await _setup(hass, BlueRetroState(available=False))
    assert hass.states.get("sensor.blueretro_firmware").state == "unavailable"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_sensor.py -v`
Expected: FAIL — sensors do not exist (states are `None`).

- [ ] **Step 3: Write `custom_components/blueretro/sensor.py`**

```python
"""BlueRetro sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from blueretro_ble import BlueRetroState

from . import BlueRetroConfigEntry
from .entity import BlueRetroEntity


@dataclass(frozen=True, kw_only=True)
class BlueRetroSensorDescription(SensorEntityDescription):
    """Describes a BlueRetro sensor."""

    value_fn: Callable[[BlueRetroState], str | int | None]


SENSORS: tuple[BlueRetroSensorDescription, ...] = (
    BlueRetroSensorDescription(
        key="firmware",
        translation_key="firmware",
        value_fn=lambda s: s.fw_version,
    ),
    BlueRetroSensorDescription(
        key="game_id",
        translation_key="game_id",
        value_fn=lambda s: s.game_id,
    ),
    BlueRetroSensorDescription(
        key="game",
        translation_key="game",
        value_fn=lambda s: s.game_name,
    ),
    BlueRetroSensorDescription(
        key="config_source",
        translation_key="config_source",
        value_fn=lambda s: s.cfg_src,
    ),
    BlueRetroSensorDescription(
        key="abi_version",
        translation_key="abi_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.abi_version,
    ),
    BlueRetroSensorDescription(
        key="bd_address",
        translation_key="bd_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.bdaddr,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlueRetroConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BlueRetro sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        BlueRetroSensor(coordinator, desc) for desc in SENSORS
    )


class BlueRetroSensor(BlueRetroEntity, SensorEntity):
    """A BlueRetro sensor."""

    entity_description: BlueRetroSensorDescription

    def __init__(self, coordinator, description: BlueRetroSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"

    @property
    def native_value(self) -> str | int | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
```

- [ ] **Step 4: Add sensor translation keys** to `custom_components/blueretro/strings.json` (add an `entity` block at top level alongside `config`)

```json
  "entity": {
    "sensor": {
      "firmware": { "name": "Firmware" },
      "game_id": { "name": "Game ID" },
      "game": { "name": "Game" },
      "config_source": { "name": "Config source" },
      "abi_version": { "name": "ABI version" },
      "bd_address": { "name": "BD address" }
    }
  }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/integration/test_sensor.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add custom_components/blueretro/sensor.py custom_components/blueretro/strings.json tests/integration/test_sensor.py
git commit -m "feat: add BlueRetro sensor platform"
```

---

## Task 14: Binary sensor platform

**Files:**
- Modify: `custom_components/blueretro/binary_sensor.py`
- Test: `tests/integration/test_binary_sensor.py`

- [ ] **Step 1: Write the failing test** in `tests/integration/test_binary_sensor.py`

```python
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from blueretro_ble import BlueRetroState
from custom_components.blueretro.const import DOMAIN


async def _setup(hass, state):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_update",
            AsyncMock(return_value=state),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_config_available_on_when_idle(hass):
    await _setup(hass, BlueRetroState(available=True))
    assert (
        hass.states.get("binary_sensor.blueretro_config_available").state == "on"
    )


async def test_config_available_off_when_busy(hass):
    await _setup(hass, BlueRetroState(available=False))
    assert (
        hass.states.get("binary_sensor.blueretro_config_available").state == "off"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_binary_sensor.py -v`
Expected: FAIL — binary sensor does not exist.

- [ ] **Step 3: Write `custom_components/blueretro/binary_sensor.py`**

```python
"""BlueRetro binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BlueRetroConfigEntry
from .entity import BlueRetroEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlueRetroConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BlueRetro connectivity binary sensor."""
    async_add_entities([BlueRetroConfigAvailable(entry.runtime_data)])


class BlueRetroConfigAvailable(BlueRetroEntity, BinarySensorEntity):
    """On when the adapter is idle and reachable over BLE."""

    _attr_translation_key = "config_available"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_config_available"

    @property
    def available(self) -> bool:
        # This sensor reports reachability, so it stays available itself.
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.available)
```

- [ ] **Step 4: Add the translation key** to `custom_components/blueretro/strings.json` under `entity` (add a `binary_sensor` block alongside `sensor`)

```json
    "binary_sensor": {
      "config_available": { "name": "Config available" }
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/integration/test_binary_sensor.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add custom_components/blueretro/binary_sensor.py custom_components/blueretro/strings.json tests/integration/test_binary_sensor.py
git commit -m "feat: add config-available binary sensor"
```

---

## Task 15: Button platform

**Files:**
- Modify: `custom_components/blueretro/button.py`
- Test: `tests/integration/test_button.py`

- [ ] **Step 1: Write the failing test** in `tests/integration/test_button.py`

```python
from unittest.mock import AsyncMock, patch

from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest

from blueretro_ble import BlueRetroState
from custom_components.blueretro.const import DOMAIN


async def _setup(hass, ble_device):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_update",
            AsyncMock(return_value=BlueRetroState(available=True)),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_reboot_button_calls_device(hass):
    ble_device = AsyncMock()
    await _setup(hass, ble_device)
    with patch(
        "custom_components.blueretro.coordinator.BlueRetroDevice.async_reboot",
        AsyncMock(),
    ) as mock_reboot:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.blueretro_reboot"},
            blocking=True,
        )
    mock_reboot.assert_awaited_once_with(ble_device)


async def test_deep_sleep_button_calls_device(hass):
    ble_device = AsyncMock()
    await _setup(hass, ble_device)
    with patch(
        "custom_components.blueretro.coordinator.BlueRetroDevice.async_deep_sleep",
        AsyncMock(),
    ) as mock_sleep:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.blueretro_deep_sleep"},
            blocking=True,
        )
    mock_sleep.assert_awaited_once_with(ble_device)


async def test_button_raises_when_device_unreachable(hass):
    await _setup(hass, None)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.blueretro_reboot"},
            blocking=True,
        )
```

Note: `_setup` patches `async_ble_device_from_address` to return the given object for the
whole test; the third test passes `None` so the button finds no device.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_button.py -v`
Expected: FAIL — buttons do not exist.

- [ ] **Step 3: Write `custom_components/blueretro/button.py`**

```python
"""BlueRetro buttons."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from blueretro_ble import BlueRetroDevice

from . import BlueRetroConfigEntry
from .coordinator import BlueRetroCoordinator
from .entity import BlueRetroEntity


@dataclass(frozen=True, kw_only=True)
class BlueRetroButtonDescription(ButtonEntityDescription):
    """Describes a BlueRetro button."""

    press_fn: Callable[[BlueRetroDevice, object], Awaitable[None]]


BUTTONS: tuple[BlueRetroButtonDescription, ...] = (
    BlueRetroButtonDescription(
        key="reboot",
        translation_key="reboot",
        press_fn=lambda device, ble: device.async_reboot(ble),
    ),
    BlueRetroButtonDescription(
        key="deep_sleep",
        translation_key="deep_sleep",
        press_fn=lambda device, ble: device.async_deep_sleep(ble),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlueRetroConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BlueRetro buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        BlueRetroButton(coordinator, desc) for desc in BUTTONS
    )


class BlueRetroButton(BlueRetroEntity, ButtonEntity):
    """A BlueRetro action button."""

    entity_description: BlueRetroButtonDescription

    def __init__(
        self,
        coordinator: BlueRetroCoordinator,
        description: BlueRetroButtonDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"

    @property
    def available(self) -> bool:
        # Buttons stay enabled so the user can attempt an action; the press
        # itself reports if the device is unreachable.
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        ble_device = self.coordinator.ble_device()
        if ble_device is None:
            raise HomeAssistantError(
                "BlueRetro is busy or out of range (only reachable when idle)"
            )
        await self.entity_description.press_fn(
            self.coordinator.device, ble_device
        )
```

- [ ] **Step 4: Add button translation keys** to `custom_components/blueretro/strings.json` under `entity` (add a `button` block alongside `sensor` and `binary_sensor`)

```json
    "button": {
      "reboot": { "name": "Reboot" },
      "deep_sleep": { "name": "Deep sleep" }
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/integration/test_button.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add custom_components/blueretro/button.py custom_components/blueretro/strings.json tests/integration/test_button.py
git commit -m "feat: add reboot and deep-sleep buttons"
```

---

## Task 16: HACS packaging and full-suite verification

**Files:**
- Create: `hacs.json`
- Create: `README.md`
- Test: full suite

- [ ] **Step 1: Create `hacs.json`**

```json
{
  "name": "BlueRetro",
  "content_in_root": false,
  "render_readme": true,
  "homeassistant": "2024.12.0"
}
```

- [ ] **Step 2: Create `README.md`**

```markdown
# BlueRetro for Home Assistant

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
```

- [ ] **Step 3: Run the entire test suite**

Run: `pytest -v`
Expected: PASS — every library and integration test green.

- [ ] **Step 4: Verify HA can import the integration cleanly**

Run:
```bash
python -c "import json; json.load(open('custom_components/blueretro/manifest.json')); print('manifest ok')"
python -c "import json; json.load(open('custom_components/blueretro/strings.json')); print('strings ok')"
```
Expected: prints `manifest ok` and `strings ok`.

- [ ] **Step 5: Commit**

```bash
git add hacs.json README.md
git commit -m "docs: add HACS packaging and README"
```

---

## Notes for the implementer

- **Device verification:** The protocol is reverse-engineered from the official web config. Once
  the integration loads, confirm against the real adapter that `...a06/a09/a0c` read directly and
  that `cfg_src` (`0x05`) returns a single meaningful byte. If `cfg_src` turns out to be a string,
  switch its sensor `value_fn` to use `decode_string` instead of the raw int.
- **`game` sensor:** `game_name` is best-effort from the bundled `gameid.db`. Unknown IDs yield no
  state value (the sensor shows `unknown`), which is expected.
- **Editable install in CI:** the integration's `manifest.json` pins `blueretro-ble==0.1.0`; in the
  dev/test environment the library is installed editable from the repo root (`pip install -e .`),
  and `enable_custom_integrations` skips requirement installation during tests.
