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


async def test_reason_none_when_available(hass):
    await _setup(hass, BlueRetroState(available=True))
    state = hass.states.get("binary_sensor.blueretro_config_available")
    assert state.attributes["reason"] is None


async def test_reason_when_connect_or_read_failed(hass):
    """Device resolved but the library reported unavailable -> connect/read msg."""
    await _setup(hass, BlueRetroState(available=False))
    state = hass.states.get("binary_sensor.blueretro_config_available")
    assert "connection or config" in state.attributes["reason"]


async def test_reason_when_no_connectable_path(hass):
    """No connectable BLEDevice -> the BLE-path message; library never called."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)
    update = AsyncMock()
    with (
        patch(
            "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_update",
            update,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.blueretro_config_available")
    assert state.state == "off"
    assert "connectable Bluetooth path" in state.attributes["reason"]
    update.assert_not_called()
