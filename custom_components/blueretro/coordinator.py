"""Polling coordinator for a BlueRetro device."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from blueretro_ble import BlueRetroDevice, BlueRetroState

from .const import (
    CONF_OUTPUT_PORTS,
    CONF_SCAN_INTERVAL,
    DEFAULT_OUTPUT_PORTS,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class BlueRetroCoordinator(DataUpdateCoordinator[BlueRetroState]):
    """Polls a BlueRetro adapter while it is idle/connectable."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        minutes = entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=minutes),
        )
        self.address: str = entry.unique_id
        self.output_ports: int = entry.options.get(
            CONF_OUTPUT_PORTS, DEFAULT_OUTPUT_PORTS
        )
        self.device = BlueRetroDevice()
        # Human-readable reason the adapter is unavailable, surfaced as an
        # attribute on the config-available sensor. ``None`` while reachable.
        self.last_error: str | None = None

    async def _async_update_data(self) -> BlueRetroState:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            self.last_error = (
                "No connectable Bluetooth path to the adapter. It is out of "
                "range, powered off, busy with a controller, or only seen by a "
                "passive (non-connectable) scanner/proxy. A connectable adapter "
                "or ESPHome Bluetooth proxy must be in range while the adapter "
                "is idle."
            )
            _LOGGER.debug("BlueRetro %s unavailable: %s", self.address, self.last_error)
            return BlueRetroState(available=False)
        state = await self.device.async_update(
            ble_device, output_ports=self.output_ports
        )
        if state.available:
            self.last_error = None
        else:
            self.last_error = (
                "Found the adapter over Bluetooth but the connection or config "
                "read failed. The adapter is most likely busy (a controller is "
                "connected) or the BLE link is unstable. Enable debug logging "
                "for 'blueretro_ble.device' to see the exact BLE error."
            )
            _LOGGER.debug("BlueRetro %s unavailable: %s", self.address, self.last_error)
        return state

    def ble_device(self):
        """Return the current connectable BLEDevice or None."""
        return bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
