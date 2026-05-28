"""BlueRetro sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from blueretro_ble import BlueRetroState

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
        value_fn=lambda s: s.game_name,
    ),
    BlueRetroSensorDescription(
        key="config_source",
        translation_key="config_source",
        value_fn=lambda s: s.cfg_src,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlueRetroConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BlueRetro sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        BlueRetroSensor(coordinator, desc) for desc in SENSORS
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
