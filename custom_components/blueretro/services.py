"""BlueRetro services: config files, input mapping and memory cards.

Memory-card transfers (Dreamcast VMU, N64 Controller Pak) work at any MTU: the
library resumes after link drops, a small MTU only makes them slower. OTA is
still not exposed here.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
import time
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

from blueretro_ble import (
    PAK_SIZE,
    VMU_SIZE,
    InputMapping,
    list_presets,
    load_preset,
    parse_firmware,
)

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import BlueRetroCoordinator

SERVICE_LIST_FILES = "list_config_files"
SERVICE_DELETE_FILE = "delete_config_file"
SERVICE_GET_MAPPING = "get_input_mapping"
SERVICE_SET_MAPPING = "set_input_mapping"
SERVICE_LIST_PRESETS = "list_presets"
SERVICE_APPLY_PRESET = "apply_preset"
SERVICE_BACKUP_CARD = "backup_memory_card"
SERVICE_RESTORE_CARD = "restore_memory_card"
SERVICE_FORMAT_PAK = "format_controller_pak"

ATTR_DEVICE_ID = "device_id"
ATTR_NAME = "name"
ATTR_CONFIG_ID = "config_id"
ATTR_MAPPINGS = "mappings"
ATTR_PRESET = "preset"
ATTR_PORT = "port"
ATTR_CARD = "card"
ATTR_BANK = "bank"
ATTR_PATH = "path"

CARD_VMU = "vmu"
CARD_PAK = "controller_pak"
# Image size and file extension per card type.
_CARDS = {CARD_VMU: (VMU_SIZE, "vmu"), CARD_PAK: (PAK_SIZE, "mpk")}
_PLATFORM_CARD = {"Dreamcast": CARD_VMU, "N64": CARD_PAK}
# The firmware persists the memory card asynchronously: 1 s after the last
# write, then one 4 KiB block every 20 ms (memory_card.c). Wait that out so a
# reboot/power-off sequenced after the service cannot cut the flush.
FLUSH_SECONDS = 5

_CARD_FIELDS = {
    vol.Optional(ATTR_CARD): vol.In(list(_CARDS)),
    vol.Optional(ATTR_BANK, default=1): vol.All(int, vol.Range(min=1, max=4)),
}

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


def _card(coordinator: BlueRetroCoordinator, call: ServiceCall) -> str:
    """Card type from the call, else inferred from the adapter's firmware."""
    if card := call.data.get(ATTR_CARD):
        return card
    fw = coordinator.data.fw_version if coordinator.data else None
    if card := _PLATFORM_CARD.get(parse_firmware(fw)[2] or ""):
        return card
    raise HomeAssistantError(
        "Cannot tell the memory card type of this adapter; set `card`"
    )


async def _card_io(coordinator: BlueRetroCoordinator, card: str, bank: int, data=None):
    """Read (``data is None``) or write the card while holding the BLE lock."""
    device = coordinator.device
    async with coordinator.lock:
        ble = _ble(coordinator)
        try:
            if card == CARD_VMU:
                if data is None:
                    return await device.async_read_vmu(ble)
                return await device.async_write_vmu(ble, data)
            if data is None:
                return await device.async_read_pak(ble, bank - 1)
            return await device.async_write_pak(ble, bank - 1, data)
        except RuntimeError as err:
            raise HomeAssistantError(f"Memory card transfer failed: {err}") from err


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

    async def presets(call: ServiceCall) -> ServiceResponse:
        out = []
        for pid in list_presets():
            p = load_preset(pid)
            out.append(
                {"id": pid, "name": p.name, "console": p.console, "desc": p.desc}
            )
        return {"presets": out}

    async def apply_preset(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        try:
            preset = load_preset(call.data[ATTR_PRESET])
        except KeyError as err:
            raise HomeAssistantError(
                f"Unknown preset {call.data[ATTR_PRESET]!r}; see list_presets"
            ) from err
        await coordinator.device.async_apply_preset(
            _ble(coordinator),
            preset,
            cfg_id=call.data[ATTR_CONFIG_ID],
            port=call.data[ATTR_PORT],
        )

    async def backup_card(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        card, bank = _card(coordinator, call), call.data[ATTR_BANK]
        start = time.monotonic()
        data = await _card_io(coordinator, card, bank)
        name = coordinator.adv_name or coordinator.title or coordinator.address
        suffix = f"_bank{bank}" if card == CARD_PAK else ""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        # Media dirs are allowlisted by default, so backups are restorable and
        # browsable; www/ would serve them publicly.
        media = next(iter(hass.config.media_dirs.values()), hass.config.path("media"))
        path = Path(media) / DOMAIN / (
            f"{name}{suffix}_{stamp}.{_CARDS[card][1]}".replace(":", "")
        )

        def _save() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await hass.async_add_executor_job(_save)
        return {
            "path": str(path),
            "size": len(data),
            "seconds": round(time.monotonic() - start, 1),
        }

    async def restore_card(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        card, bank = _card(coordinator, call), call.data[ATTR_BANK]
        path = call.data[ATTR_PATH]
        if not hass.config.is_allowed_path(path):
            raise HomeAssistantError(f"{path} is not in allowlist_external_dirs")
        try:
            data = await hass.async_add_executor_job(Path(path).read_bytes)
        except OSError as err:
            raise HomeAssistantError(f"Cannot read {path}: {err}") from err
        if len(data) != _CARDS[card][0]:
            raise HomeAssistantError(
                f"{path} is {len(data)} bytes; a {card} image is {_CARDS[card][0]}"
            )
        await _card_io(coordinator, card, bank, data)
        await asyncio.sleep(FLUSH_SECONDS)

    async def format_pak(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        async with coordinator.lock:
            await coordinator.device.async_format_pak(
                _ble(coordinator), call.data[ATTR_BANK] - 1
            )
        await asyncio.sleep(FLUSH_SECONDS)

    hass.services.async_register(
        DOMAIN,
        SERVICE_BACKUP_CARD,
        backup_card,
        schema=vol.Schema({**_DEVICE, **_CARD_FIELDS}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTORE_CARD,
        restore_card,
        schema=vol.Schema(
            {**_DEVICE, **_CARD_FIELDS, vol.Required(ATTR_PATH): cv.string}
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FORMAT_PAK,
        format_pak,
        schema=vol.Schema(
            {
                **_DEVICE,
                vol.Optional(ATTR_BANK, default=1): vol.All(int, vol.Range(min=1, max=4)),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_PRESETS,
        presets,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_PRESET,
        apply_preset,
        schema=vol.Schema(
            {
                **_DEVICE,
                vol.Required(ATTR_PRESET): cv.string,
                vol.Optional(ATTR_CONFIG_ID, default=0): vol.All(
                    int, vol.Range(min=0)
                ),
                vol.Optional(ATTR_PORT, default=0): vol.All(
                    int, vol.Range(min=0, max=11)
                ),
            }
        ),
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
