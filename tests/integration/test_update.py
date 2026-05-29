from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.helpers.entity_component import async_update_entity
from pytest_homeassistant_custom_component.common import MockConfigEntry

from blueretro_ble import BlueRetroState
from custom_components.blueretro.const import DOMAIN

BLE_ADDR = "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address"
UPDATE = "custom_components.blueretro.coordinator.BlueRetroDevice.async_update"
SESSION = "custom_components.blueretro.update.async_get_clientsession"
ENTITY = "update.blueretro_firmware"


def _github_session(tag: str = "v9.9.9", status: int = 200) -> MagicMock:
    """Fake aiohttp session whose GET returns one GitHub release payload."""
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(
        return_value={"tag_name": tag, "html_url": "https://example/release"}
    )
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.get = MagicMock(return_value=cm)
    return session


async def _setup(hass, fw_version: str) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="AA:BB:CC:DD:EE:FF", data={}
    )
    entry.add_to_hass(hass)
    state = BlueRetroState(available=True, fw_version=fw_version)
    with (
        patch(BLE_ADDR, return_value=AsyncMock()),
        patch(UPDATE, AsyncMock(return_value=state)),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_update_available_when_github_newer(hass):
    with patch(SESSION, return_value=_github_session("v9.9.9")):
        await _setup(hass, "v1.8.1_master_dc_0c5d35d")
        await async_update_entity(hass, ENTITY)
        await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state is not None
    assert state.attributes["installed_version"] == "1.8.1"
    assert state.attributes["latest_version"] == "9.9.9"
    assert state.state == "on"


async def test_no_false_update_when_github_unreachable(hass):
    # A failed fetch must leave latest mirroring installed, so no update shows.
    with patch(SESSION, return_value=_github_session(status=500)):
        await _setup(hass, "v1.8.1_master_dc_0c5d35d")
        await async_update_entity(hass, ENTITY)
        await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state is not None
    assert state.attributes["latest_version"] == "1.8.1"
    assert state.state == "off"
