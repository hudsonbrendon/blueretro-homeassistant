from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from blueretro_ble import BlueRetroState
from custom_components.blueretro.const import DOMAIN


async def _setup(hass, state):
    entry = MockConfigEntry(domain=DOMAIN, title="BlueRetro", unique_id="AA:BB:CC:DD:EE:FF", data={})
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
        await hass.async_block_till_done(wait_background_tasks=True)


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
    entry = MockConfigEntry(domain=DOMAIN, title="BlueRetro", unique_id="AA:BB:CC:DD:EE:FF", data={})
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
        await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("binary_sensor.blueretro_config_available")
    assert state.state == "off"
    assert "connectable Bluetooth path" in state.attributes["reason"]
    update.assert_not_called()


def _adv(rssi=-60, name="BlueRetro_DC_2A6E"):
    from unittest.mock import MagicMock

    info = MagicMock()
    info.name = name
    info.rssi = rssi
    return info


async def test_in_use_unavailable_until_first_advertisement(hass):
    await _setup(hass, BlueRetroState(available=True))
    assert hass.states.get("binary_sensor.blueretro_controller_connected").state == "unavailable"


async def test_in_use_follows_advertisement_presence(hass):
    await _setup(hass, BlueRetroState(available=True))
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data

    coordinator._async_seen(_adv(), None)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("binary_sensor.blueretro_controller_connected")
    assert state.state == "off"
    assert state.attributes["last_seen"] is not None
    assert coordinator.rssi == -60

    coordinator._async_gone(_adv())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("binary_sensor.blueretro_controller_connected").state == "on"


async def test_advertisement_back_triggers_refresh(hass):
    await _setup(hass, BlueRetroState(available=True))
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    coordinator._async_gone(_adv())
    with patch.object(coordinator, "async_request_refresh", AsyncMock()) as refresh:
        coordinator._async_seen(_adv(), None)
        await hass.async_block_till_done(wait_background_tasks=True)
    refresh.assert_awaited_once()
