"""Polling coordinator for a BlueRetro device."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from blueretro_ble import BlueRetroDevice, BlueRetroState, parse_firmware

from .const import (
    CONF_OUTPUT_PORTS,
    CONF_SCAN_INTERVAL,
    DEFAULT_OUTPUT_PORTS,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Upper bound for one connect-and-read; bleak-retry-connector's own retries
# and backoff can otherwise pin a poll for many minutes.
POLL_TIMEOUT = 120


class BlueRetroCoordinator(DataUpdateCoordinator[BlueRetroState]):
    """Polls a BlueRetro adapter while it is idle/connectable.

    Besides the periodic connect-and-read poll, it listens passively to the
    adapter's advertisements. The firmware only advertises while no controller
    is connected (it stops advertising when one connects and resumes when it
    disconnects), so "advertisement gone" == "in use" and "advertisement back"
    == "idle again" -- both without opening a connection.
    """

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
        # Entry title is the advertised local name captured at discovery.
        self.title: str | None = entry.title
        self.output_ports: int = entry.options.get(
            CONF_OUTPUT_PORTS, DEFAULT_OUTPUT_PORTS
        )
        self.device = BlueRetroDevice()
        # Human-readable reason the adapter is unavailable, surfaced as an
        # attribute on the config-available sensor. ``None`` while reachable.
        self.last_error: str | None = None
        # Passive advertisement tracking.
        self.adv_name: str | None = None
        self.rssi: int | None = None
        self.last_seen: datetime | None = None
        # True once HA reports the advertisement gone (controller connected,
        # or powered off -- indistinguishable without a connection).
        self.in_use: bool = False
        info = bluetooth.async_last_service_info(
            hass, self.address, connectable=False
        )
        if info is not None:
            self._record(info)

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Subscribe to advertisement seen/gone events; returns the unsubscribe."""
        unsub_seen = bluetooth.async_register_callback(
            self.hass,
            self._async_seen,
            {"address": self.address, "connectable": False},
            BluetoothScanningMode.PASSIVE,
        )
        unsub_gone = bluetooth.async_track_unavailable(
            self.hass, self._async_gone, self.address, connectable=False
        )

        @callback
        def _unsub() -> None:
            unsub_seen()
            unsub_gone()

        return _unsub

    def _record(self, info: BluetoothServiceInfoBleak) -> None:
        self.adv_name = info.name
        self.rssi = info.rssi
        self.last_seen = dt_util.utcnow()

    @callback
    def _async_sync_device(self, state: BlueRetroState | None = None) -> None:
        """Push late-arriving facts (adv name, firmware) into the device registry.

        Entities register the device before the first BLE read (setup never
        blocks on Bluetooth) and possibly before the adapter advertises, so the
        registry is refreshed here instead. ``name`` is the integration-provided
        name; a user rename (``name_by_user``) is untouched.
        """
        reg = dr.async_get(self.hass)
        device = reg.async_get_device(identifiers={(DOMAIN, self.address)})
        if device is None:
            return
        changes: dict[str, str] = {}
        if self.adv_name and device.name != self.adv_name:
            changes["name"] = self.adv_name
        if state is not None and state.available:
            sw, hw, platform = parse_firmware(state.fw_version)
            model = f"BlueRetro ({platform})" if platform else "BlueRetro"
            for key, value in (("sw_version", sw), ("hw_version", hw), ("model", model)):
                if value and getattr(device, key) != value:
                    changes[key] = value
        if changes:
            reg.async_update_device(device.id, **changes)

    @callback
    def _async_seen(
        self, info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        self._record(info)
        self._async_sync_device()
        was_in_use = self.in_use
        self.in_use = False
        if was_in_use:
            # Idle again: the game/config may have changed, read it now instead
            # of waiting for the next scheduled poll.
            self.hass.async_create_task(self.async_request_refresh())
        self.async_update_listeners()

    @callback
    def _async_gone(self, info: BluetoothServiceInfoBleak) -> None:
        self.in_use = True
        self.async_update_listeners()

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
        try:
            async with asyncio.timeout(POLL_TIMEOUT):
                state = await self.device.async_update(
                    ble_device, output_ports=self.output_ports
                )
        except TimeoutError:
            self.last_error = (
                f"Connecting to the adapter took longer than {POLL_TIMEOUT}s. "
                "The Bluetooth host may be holding a stale connection; it "
                "usually clears on the next poll."
            )
            _LOGGER.debug("BlueRetro %s unavailable: %s", self.address, self.last_error)
            return BlueRetroState(available=False)
        if state.available:
            self.last_error = None
            self._async_sync_device(state)
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
