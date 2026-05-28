from unittest.mock import AsyncMock, patch

from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest

from blueretro_ble import BlueRetroState
from custom_components.blueretro.const import DOMAIN

BLE_ADDR = "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address"
UPDATE = "custom_components.blueretro.coordinator.BlueRetroDevice.async_update"


async def _setup(hass, ble_device, state):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)
    with (
        patch(BLE_ADDR, return_value=ble_device),
        patch(UPDATE, AsyncMock(return_value=state)),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_selects_show_current_option(hass):
    state = BlueRetroState(available=True, controller_mode="Keyboard", accessory="Both")
    await _setup(hass, AsyncMock(), state)
    assert hass.states.get("select.blueretro_controller_mode").state == "Keyboard"
    assert hass.states.get("select.blueretro_accessory").state == "Both"


async def test_select_accessory_writes_output_config(hass):
    ble_device = AsyncMock()
    state = BlueRetroState(available=True, controller_mode="GamePad", accessory="None")
    with (
        patch(BLE_ADDR, return_value=ble_device),
        patch(UPDATE, AsyncMock(return_value=state)),
    ):
        await _setup(hass, ble_device, state)
        with patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_set_output_config",
            AsyncMock(),
        ) as mock_set:
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": "select.blueretro_accessory", "option": "Memory"},
                blocking=True,
            )
    mock_set.assert_awaited_once_with(ble_device, 0, accessory="Memory")


async def test_select_raises_when_device_unreachable(hass):
    state = BlueRetroState(available=True, controller_mode="GamePad", accessory="None")
    with (
        patch(BLE_ADDR, return_value=None),
        patch(UPDATE, AsyncMock(return_value=state)),
    ):
        await _setup(hass, None, state)
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": "select.blueretro_controller_mode", "option": "Mouse"},
                blocking=True,
            )


async def test_select_memory_card_bank_writes_global_config(hass):
    ble_device = AsyncMock()
    state = BlueRetroState(available=True, system="N64", memory_card_bank=1)
    with (
        patch(BLE_ADDR, return_value=ble_device),
        patch(UPDATE, AsyncMock(return_value=state)),
    ):
        await _setup(hass, ble_device, state)
        assert hass.states.get("select.blueretro_memory_card_bank").state == "1"
        with patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_set_global_config",
            AsyncMock(),
        ) as mock_set:
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": "select.blueretro_memory_card_bank", "option": "3"},
                blocking=True,
            )
    mock_set.assert_awaited_once_with(ble_device, memory_card_bank=3)
