from unittest.mock import AsyncMock, patch

from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from blueretro_ble import BlueRetroState
from custom_components.blueretro._firmware import parse_firmware
from custom_components.blueretro.const import DOMAIN


def test_parse_firmware_full():
    assert parse_firmware("v24.04 hw1 playstation") == (
        "v24.04",
        "hw1",
        "Playstation",
    )


def test_parse_firmware_no_hw():
    assert parse_firmware("v1.8.1 gamecube") == ("v1.8.1", None, "Gamecube")


def test_parse_firmware_version_only():
    assert parse_firmware("v1.8.1") == ("v1.8.1", None, None)


def test_parse_firmware_empty():
    assert parse_firmware(None) == (None, None, None)
    assert parse_firmware("") == (None, None, None)


async def test_device_info_split_from_firmware(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)
    state = BlueRetroState(available=True, fw_version="v24.04 hw1 playstation")
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

    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, "AA:BB:CC:DD:EE:FF")}
    )
    assert device is not None
    assert device.model == "BlueRetro (Playstation)"
    assert device.sw_version == "v24.04"
    assert device.hw_version == "hw1"
