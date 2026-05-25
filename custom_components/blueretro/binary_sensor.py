"""BlueRetro binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    async_add_entities([BlueRetroConfigAvailable(entry.runtime_data)])


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
