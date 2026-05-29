"""BlueRetro services: config-file manager and advanced input mapping.

These are the "small payload" operations that have a chance of working over
Home Assistant's Bluetooth stack; large transfers (VMU/pak/OTA) need a high
negotiated MTU and are intentionally not exposed here.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
import voluptuous as vol

from blueretro_ble import InputMapping

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import BlueRetroCoordinator

SERVICE_LIST_FILES = "list_config_files"
SERVICE_DELETE_FILE = "delete_config_file"
SERVICE_GET_MAPPING = "get_input_mapping"
SERVICE_SET_MAPPING = "set_input_mapping"

ATTR_DEVICE_ID = "device_id"
ATTR_NAME = "name"
ATTR_CONFIG_ID = "config_id"
ATTR_MAPPINGS = "mappings"

_MAPPING_SCHEMA = vol.Schema(
    {
        vol.Required("src"): vol.All(int, vol.Range(min=0, max=255)),
        vol.Required("dest"): vol.All(int, vol.Range(min=0, max=255)),
        vol.Optional("dest_id", default=0): vol.All(int, vol.Range(min=0, max=255)),
        vol.Optional("max", default=0): vol.All(int, vol.Range(min=0, max=255)),
        vol.Optional("threshold", default=0): vol.All(int, vol.Range(min=0, max=255)),
        vol.Optional("deadzone", default=0): vol.All(int, vol.Range(min=0, max=255)),
        vol.Optional("turbo", default=0): vol.All(int, vol.Range(min=0, max=255)),
        vol.Optional("scaling", default=0): vol.All(int, vol.Range(min=0, max=15)),
        vol.Optional("diag_scaling", default=0): vol.All(int, vol.Range(min=0, max=15)),
    }
)

_DEVICE = {vol.Required(ATTR_DEVICE_ID): cv.string}


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> BlueRetroCoordinator:
    """Resolve the BlueRetro coordinator targeted by ``device_id``."""
    device_id = call.data[ATTR_DEVICE_ID]
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise HomeAssistantError(f"Unknown device {device_id}")
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry and entry.domain == DOMAIN and entry.state.recoverable:
            return entry.runtime_data
    raise HomeAssistantError(f"{device_id} is not a BlueRetro device")


def _ble(coordinator: BlueRetroCoordinator):
    ble_device = coordinator.ble_device()
    if ble_device is None:
        raise HomeAssistantError(
            "BlueRetro is busy or out of range (only reachable when idle)"
        )
    return ble_device


def async_setup_services(hass: HomeAssistant) -> None:
    """Register BlueRetro domain services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_LIST_FILES):
        return

    async def list_files(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        files = await coordinator.device.async_list_files(_ble(coordinator))
        return {"files": files}

    async def delete_file(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        await coordinator.device.async_delete_file(
            _ble(coordinator), call.data[ATTR_NAME]
        )

    async def get_mapping(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        mappings = await coordinator.device.async_read_input_config(
            _ble(coordinator), call.data[ATTR_CONFIG_ID]
        )
        return {"mappings": [asdict(m) for m in mappings]}

    async def set_mapping(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        mappings = [InputMapping(**m) for m in call.data[ATTR_MAPPINGS]]
        await coordinator.device.async_write_input_config(
            _ble(coordinator), call.data[ATTR_CONFIG_ID], mappings
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_FILES,
        list_files,
        schema=vol.Schema(_DEVICE),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_FILE,
        delete_file,
        schema=vol.Schema({**_DEVICE, vol.Required(ATTR_NAME): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_MAPPING,
        get_mapping,
        schema=vol.Schema(
            {**_DEVICE, vol.Required(ATTR_CONFIG_ID): vol.All(int, vol.Range(min=0))}
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MAPPING,
        set_mapping,
        schema=vol.Schema(
            {
                **_DEVICE,
                vol.Required(ATTR_CONFIG_ID): vol.All(int, vol.Range(min=0)),
                vol.Required(ATTR_MAPPINGS): vol.All(
                    cv.ensure_list, [_MAPPING_SCHEMA]
                ),
            }
        ),
    )
