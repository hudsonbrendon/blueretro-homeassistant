"""BlueRetro sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from blueretro_ble import SYSTEM_CFG, BlueRetroState

from . import BlueRetroConfigEntry
from .entity import BlueRetroEntity


@dataclass(frozen=True, kw_only=True)
class BlueRetroSensorDescription(SensorEntityDescription):
    """Describes a BlueRetro sensor."""

    value_fn: Callable[[BlueRetroState], str | int | None]


SENSORS: tuple[BlueRetroSensorDescription, ...] = (
    BlueRetroSensorDescription(
        key="firmware",
        translation_key="firmware",
        value_fn=lambda s: s.fw_version,
    ),
    BlueRetroSensorDescription(
        key="game_id",
        translation_key="game_id",
        value_fn=lambda s: s.game_id,
    ),
    BlueRetroSensorDescription(
        key="game",
        translation_key="game",
        # Firmware reports the system name (e.g. "GC") as the game id while
        # no game is running; that is not a game, so show unknown.
        value_fn=lambda s: None if not _game_running(s) else s.game_name,
    ),
    BlueRetroSensorDescription(
        key="abi_version",
        translation_key="abi_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.abi_version,
    ),
    BlueRetroSensorDescription(
        key="bd_address",
        translation_key="bd_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.bdaddr,
    ),
    BlueRetroSensorDescription(
        key="firmware_name",
        translation_key="firmware_name",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.fw_name,
    ),
)


def _game_running(state: BlueRetroState) -> bool:
    """True when the reported game id is a real game, not the system name."""
    return bool(state.game_id) and state.game_id not in SYSTEM_CFG


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlueRetroConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BlueRetro sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(BlueRetroSensor(coordinator, desc) for desc in SENSORS),
            BlueRetroRssiSensor(coordinator),
        ]
    )


class BlueRetroSensor(BlueRetroEntity, SensorEntity):
    """A BlueRetro sensor."""

    entity_description: BlueRetroSensorDescription

    def __init__(self, coordinator, description: BlueRetroSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"

    @property
    def native_value(self) -> str | int | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, bool] | None:
        if self.entity_description.key != "game" or self.coordinator.data is None:
            return None
        return {"game_running": _game_running(self.coordinator.data)}


class BlueRetroRssiSensor(BlueRetroEntity, SensorEntity):
    """Signal strength from the last advertisement (passive, no connection)."""

    _attr_translation_key = "rssi"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_rssi"

    @property
    def available(self) -> bool:
        return self.coordinator.rssi is not None

    @property
    def native_value(self) -> int | None:
        return self.coordinator.rssi
