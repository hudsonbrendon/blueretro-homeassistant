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
