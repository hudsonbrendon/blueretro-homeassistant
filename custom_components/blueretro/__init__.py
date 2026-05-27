"""The BlueRetro integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import BlueRetroCoordinator

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
]

type BlueRetroConfigEntry = ConfigEntry[BlueRetroCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: BlueRetroConfigEntry
) -> bool:
    """Set up BlueRetro from a config entry."""
    coordinator = BlueRetroCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BlueRetroConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
