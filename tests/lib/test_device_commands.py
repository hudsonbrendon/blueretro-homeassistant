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
