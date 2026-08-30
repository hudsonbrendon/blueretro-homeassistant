"""BlueRetro binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BlueRetroConfigEntry
from .entity import BlueRetroEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlueRetroConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BlueRetro connectivity binary sensor."""
    coordinator = entry.runtime_data
    async_add_entities(
        [BlueRetroConfigAvailable(coordinator), BlueRetroInUse(coordinator)]
    )


class BlueRetroConfigAvailable(BlueRetroEntity, BinarySensorEntity):
    """On when the adapter is idle and reachable over BLE."""

    _attr_translation_key = "config_available"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_config_available"

    @property
    def available(self) -> bool:
        # This sensor reports reachability, so it stays available itself.
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.available)

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        # Surface *why* the adapter is unreachable so it can be diagnosed from
        # the UI without enabling debug logging. ``None`` while reachable.
        return {"reason": self.coordinator.last_error}


class BlueRetroInUse(BlueRetroEntity, BinarySensorEntity):
    """On while a controller is connected to the adapter (advertisement gone).

    Derived passively from the advertisement the firmware only emits while
    idle, so it needs no BLE connection and updates within HA's unavailable
    tracking window (~1 min) when a controller connects, and immediately when
    it disconnects. Powered-off looks the same as in-use; check ``last_seen``.
    """

    _attr_translation_key = "in_use"
    _attr_icon = "mdi:controller"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_in_use"

    @property
    def available(self) -> bool:
        # Passive: meaningful even while the config interface is unreachable.
        return self.coordinator.last_seen is not None

    @property
    def is_on(self) -> bool:
        return self.coordinator.in_use

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        seen = self.coordinator.last_seen
        return {"last_seen": seen.isoformat() if seen else None}
