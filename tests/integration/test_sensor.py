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
        fw_name="playstation hw1",
        abi_version=2,
        bdaddr="66:55:44:33:22:11",
        game_id="GALE01",
        game_name="Super Smash Bros. Melee",
        cfg_src=1,
        system="PS2",
        multitap="None",
        inquiry_mode="Manual",
        memory_card_bank=1,
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
    assert (
        hass.states.get("sensor.blueretro_firmware_name").state
        == "playstation hw1"
    )


async def test_sensors_unavailable_when_offline(hass):
    await _setup(hass, BlueRetroState(available=False))
    assert hass.states.get("sensor.blueretro_firmware").state == "unavailable"
