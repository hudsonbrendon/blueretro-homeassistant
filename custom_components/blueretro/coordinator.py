"""Polling coordinator for a BlueRetro device."""

from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from blueretro_ble import BlueRetroDevice, BlueRetroState

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class BlueRetroCoordinator(DataUpdateCoordinator[BlueRetroState]):
    """Polls a BlueRetro adapter while it is idle/connectable."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL
        )
        self.address: str = entry.unique_id
        self.device = BlueRetroDevice()

    async def _async_update_data(self) -> BlueRetroState:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            return BlueRetroState(available=False)
        return await self.device.async_update(ble_device)

    def ble_device(self):
        """Return the current connectable BLEDevice or None."""
        return bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
