from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest

from blueretro_ble import BlueRetroState, InputMapping
from custom_components.blueretro.const import DOMAIN

ADDR = "AA:BB:CC:DD:EE:FF"
BLE_ADDR = "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address"
UPDATE = "custom_components.blueretro.coordinator.BlueRetroDevice.async_update"
DEV = "custom_components.blueretro.coordinator.BlueRetroDevice"


@contextmanager
def _connected(ble_device):
    """Keep the BLE lookup + coordinator update patched for setup and call."""
    with (
        patch(BLE_ADDR, return_value=ble_device),
        patch(UPDATE, AsyncMock(return_value=BlueRetroState(available=True))),
    ):
        yield


async def _setup(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDR, data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _device_id(hass) -> str:
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, ADDR)})
    assert device is not None
    return device.id


async def test_list_config_files(hass):
    ble = AsyncMock()
    with _connected(ble):
        await _setup(hass)
        with patch(
            f"{DEV}.async_list_files",
            AsyncMock(return_value=["GALE01", "SMSE52"]),
        ):
            resp = await hass.services.async_call(
                DOMAIN,
                "list_config_files",
                {"device_id": _device_id(hass)},
                blocking=True,
                return_response=True,
            )
    assert resp == {"files": ["GALE01", "SMSE52"]}


async def test_delete_config_file(hass):
    ble = AsyncMock()
    with _connected(ble):
        await _setup(hass)
        with patch(f"{DEV}.async_delete_file", AsyncMock()) as mock_del:
            await hass.services.async_call(
                DOMAIN,
                "delete_config_file",
                {"device_id": _device_id(hass), "name": "GALE01"},
                blocking=True,
            )
    mock_del.assert_awaited_once_with(ble, "GALE01")


async def test_set_input_mapping(hass):
    ble = AsyncMock()
    with _connected(ble):
        await _setup(hass)
        with patch(
            f"{DEV}.async_write_input_config", AsyncMock()
        ) as mock_set:
            await hass.services.async_call(
                DOMAIN,
                "set_input_mapping",
                {
                    "device_id": _device_id(hass),
                    "config_id": 0,
                    "mappings": [{"src": 1, "dest": 2, "max": 255}],
                },
                blocking=True,
            )
    mock_set.assert_awaited_once_with(
        ble, 0, [InputMapping(src=1, dest=2, max=255)]
    )


async def test_get_input_mapping(hass):
    ble = AsyncMock()
    mappings = [InputMapping(src=7, dest=8, scaling=1)]
    with _connected(ble):
        await _setup(hass)
        with patch(
            f"{DEV}.async_read_input_config", AsyncMock(return_value=mappings)
        ):
            resp = await hass.services.async_call(
                DOMAIN,
                "get_input_mapping",
                {"device_id": _device_id(hass), "config_id": 0},
                blocking=True,
                return_response=True,
            )
    assert resp["mappings"][0]["src"] == 7
    assert resp["mappings"][0]["scaling"] == 1


async def test_service_raises_when_unreachable(hass):
    ble = AsyncMock()
    with _connected(ble):
        await _setup(hass)
        device_id = _device_id(hass)
    # Patch context exited: the BLE lookup now returns None (unreachable).
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "delete_config_file",
            {"device_id": device_id, "name": "GALE01"},
            blocking=True,
        )
