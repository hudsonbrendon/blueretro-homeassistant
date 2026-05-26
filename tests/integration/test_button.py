import glob
import os
from unittest.mock import AsyncMock, patch

from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest

from blueretro_ble import BlueRetroState
from custom_components.blueretro.const import DOMAIN

BLE_ADDR = "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address"
UPDATE = "custom_components.blueretro.coordinator.BlueRetroDevice.async_update"


async def _setup(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_reboot_button_calls_device(hass):
    ble_device = AsyncMock()
    # The ble_device lookup must stay patched through the button press, not just
    # during setup, since async_press() resolves the device again at press time.
    with (
        patch(BLE_ADDR, return_value=ble_device),
        patch(UPDATE, AsyncMock(return_value=BlueRetroState(available=True))),
    ):
        await _setup(hass)
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
    with (
        patch(BLE_ADDR, return_value=ble_device),
        patch(UPDATE, AsyncMock(return_value=BlueRetroState(available=True))),
    ):
        await _setup(hass)
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
    # Setup succeeds (update returns a state), but no connectable device is found
    # when the button is pressed, so the press must raise.
    with (
        patch(BLE_ADDR, return_value=None),
        patch(UPDATE, AsyncMock(return_value=BlueRetroState(available=True))),
    ):
        await _setup(hass)
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.blueretro_reboot"},
                blocking=True,
            )


async def test_backup_vmu_button_writes_file(hass):
    ble_device = AsyncMock()
    vmu = bytes(128 * 1024)
    with (
        patch(BLE_ADDR, return_value=ble_device),
        patch(UPDATE, AsyncMock(return_value=BlueRetroState(available=True))),
    ):
        await _setup(hass)
        with patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_read_vmu",
            AsyncMock(return_value=vmu),
        ) as mock_read:
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.blueretro_backup_vmu"},
                blocking=True,
            )
    mock_read.assert_awaited_once_with(ble_device)
    files = glob.glob(hass.config.path("blueretro_vmu_*.bin"))
    assert files, "expected a VMU .bin to be written"
    assert os.path.getsize(files[0]) == len(vmu)
