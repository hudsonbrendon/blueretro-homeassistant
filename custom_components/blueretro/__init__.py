"""The BlueRetro integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import BlueRetroCoordinator
from .services import async_setup_services

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.UPDATE,
]

type BlueRetroConfigEntry = ConfigEntry[BlueRetroCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: BlueRetroConfigEntry
) -> bool:
    """Set up BlueRetro from a config entry."""
    # 0.8.0 replaced the config-source sensor with a select; drop the orphan.
    ent_reg = er.async_get(hass)
    if stale := ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}_config_source"
    ):
        ent_reg.async_remove(stale)
    coordinator = BlueRetroCoordinator(hass, entry)
    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_start())
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Never block setup on a BLE connection: with several adapters (and BlueZ
    # sometimes holding a stale link) the first connect can take minutes and
    # Home Assistant cancels slow setups at boot. Poll in the background;
    # entities stay unavailable until the first read lands.
    entry.async_create_background_task(
        hass, coordinator.async_refresh(), "blueretro-first-refresh", eager_start=True
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    async_setup_services(hass)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: BlueRetroConfigEntry
) -> None:
    """Reload the entry so a changed poll interval takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: BlueRetroConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
