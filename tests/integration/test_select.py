from unittest.mock import AsyncMock, patch

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest

from blueretro_ble import BlueRetroState
from custom_components.blueretro.const import CONF_OUTPUT_PORTS, DOMAIN

ADDR = "AA:BB:CC:DD:EE:FF"
BLE_ADDR = "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address"
UPDATE = "custom_components.blueretro.coordinator.BlueRetroDevice.async_update"
SET_OUTPUT = "custom_components.blueretro.coordinator.BlueRetroDevice.async_set_output_config"


async def _setup(hass, ble_device, state, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=ADDR, data={}, options=options or {}
    )
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


async def test_only_port_0_selects_by_default(hass):
    """With the default port count, no per-port (port 2+) selects exist."""
    state = BlueRetroState(available=True, ports={0: ("GamePad", "None")})
    await _setup(hass, AsyncMock(), state)
    ent_reg = er.async_get(hass)
    assert (
        ent_reg.async_get_entity_id("select", DOMAIN, f"{ADDR}_controller_mode")
        is not None
    )
    assert (
        ent_reg.async_get_entity_id(
            "select", DOMAIN, f"{ADDR}_controller_mode_port2"
        )
        is None
    )


async def test_per_port_selects_created_and_write(hass):
    ble_device = AsyncMock()
    state = BlueRetroState(
        available=True,
        ports={0: ("GamePad", "None"), 1: ("Keyboard", "Memory")},
    )
    with (
        patch(BLE_ADDR, return_value=ble_device),
        patch(UPDATE, AsyncMock(return_value=state)),
    ):
        await _setup(hass, ble_device, state, options={CONF_OUTPUT_PORTS: 2})
        ent_reg = er.async_get(hass)
        eid_mode = ent_reg.async_get_entity_id(
            "select", DOMAIN, f"{ADDR}_controller_mode_port2"
        )
        eid_acc = ent_reg.async_get_entity_id(
            "select", DOMAIN, f"{ADDR}_accessory_port2"
        )
        assert eid_mode is not None and eid_acc is not None
        assert hass.states.get(eid_mode).state == "Keyboard"
        assert hass.states.get(eid_acc).state == "Memory"

        with patch(SET_OUTPUT, AsyncMock()) as mock_set:
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": eid_mode, "option": "Mouse"},
                blocking=True,
            )
    # Port 2 (index 1) is written.
    mock_set.assert_awaited_once_with(ble_device, 1, device="Mouse")


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


async def test_select_multitap_writes_global_config(hass):
    ble_device = AsyncMock()
    state = BlueRetroState(available=True, multitap="None")
    with (
        patch(BLE_ADDR, return_value=ble_device),
        patch(UPDATE, AsyncMock(return_value=state)),
    ):
        await _setup(hass, ble_device, state)
        assert hass.states.get("select.blueretro_multitap").state == "None"
        with patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_set_global_config",
            AsyncMock(),
        ) as mock_set:
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": "select.blueretro_multitap", "option": "Dual"},
                blocking=True,
            )
    mock_set.assert_awaited_once_with(ble_device, multitap="Dual")


async def test_select_system_writes_global_config(hass):
    ble_device = AsyncMock()
    state = BlueRetroState(available=True, system="Auto")
    with (
        patch(BLE_ADDR, return_value=ble_device),
        patch(UPDATE, AsyncMock(return_value=state)),
    ):
        await _setup(hass, ble_device, state)
        assert hass.states.get("select.blueretro_system").state == "Auto"
        with patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_set_global_config",
            AsyncMock(),
        ) as mock_set:
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": "select.blueretro_system", "option": "N64"},
                blocking=True,
            )
    mock_set.assert_awaited_once_with(ble_device, system="N64")


async def test_select_pairing_mode_writes_global_config(hass):
    ble_device = AsyncMock()
    state = BlueRetroState(available=True, inquiry_mode="Auto")
    with (
        patch(BLE_ADDR, return_value=ble_device),
        patch(UPDATE, AsyncMock(return_value=state)),
    ):
        await _setup(hass, ble_device, state)
        assert hass.states.get("select.blueretro_pairing_mode").state == "Auto"
        with patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_set_global_config",
            AsyncMock(),
        ) as mock_set:
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": "select.blueretro_pairing_mode", "option": "Manual"},
                blocking=True,
            )
    mock_set.assert_awaited_once_with(ble_device, inquiry_mode="Manual")
