"""The BlueRetro integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

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

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type BlueRetroConfigEntry = ConfigEntry[BlueRetroCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register BlueRetro services once at integration load."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BlueRetroConfigEntry) -> bool:
    """Set up BlueRetro from a config entry."""
    coordinator = BlueRetroCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BlueRetroConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
