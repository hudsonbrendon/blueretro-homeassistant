"""BlueRetro selects (per-output device mode and accessory)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from blueretro_ble import ACCESSORY_CFG, DEVICE_CFG, BlueRetroDevice, BlueRetroState

from . import BlueRetroConfigEntry
from .coordinator import BlueRetroCoordinator
from .entity import BlueRetroEntity


@dataclass(frozen=True, kw_only=True)
class BlueRetroSelectDescription(SelectEntityDescription):
    """Describes a BlueRetro select."""

    current_fn: Callable[[BlueRetroState], str | None]
    set_fn: Callable[[BlueRetroDevice, object, str], Awaitable[None]]


SELECTS: tuple[BlueRetroSelectDescription, ...] = (
    BlueRetroSelectDescription(
        key="controller_mode",
        translation_key="controller_mode",
        options=list(DEVICE_CFG),
        current_fn=lambda s: s.controller_mode,
        set_fn=lambda device, ble, opt: device.async_set_output_config(
            ble, 0, device=opt
        ),
    ),
    BlueRetroSelectDescription(
        key="accessory",
        translation_key="accessory",
        options=list(ACCESSORY_CFG),
        current_fn=lambda s: s.accessory,
        set_fn=lambda device, ble, opt: device.async_set_output_config(
            ble, 0, accessory=opt
        ),
    ),
    BlueRetroSelectDescription(
        key="memory_card_bank",
        translation_key="memory_card_bank",
        options=["1", "2", "3", "4"],
        current_fn=lambda s: (
            str(s.memory_card_bank) if s.memory_card_bank is not None else None
        ),
        # Writing the global config reboots the adapter to apply (N64-only).
        set_fn=lambda device, ble, opt: device.async_set_global_config(
            ble, memory_card_bank=int(opt)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlueRetroConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BlueRetro selects."""
    coordinator = entry.runtime_data
    async_add_entities(BlueRetroSelect(coordinator, desc) for desc in SELECTS)


class BlueRetroSelect(BlueRetroEntity, SelectEntity):
    """A BlueRetro output-config select (port 1)."""

    entity_description: BlueRetroSelectDescription

    def __init__(
        self,
        coordinator: BlueRetroCoordinator,
        description: BlueRetroSelectDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_options = list(description.options or [])

    @property
    def available(self) -> bool:
        # Stay actionable while the coordinator is polling; the write itself
        # reports if the device is unreachable at that moment.
        return self.coordinator.last_update_success

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.current_fn(self.coordinator.data)

    async def async_select_option(self, option: str) -> None:
        ble_device = self.coordinator.ble_device()
        if ble_device is None:
            raise HomeAssistantError(
                "BlueRetro is busy or out of range (only reachable when idle)"
            )
        await self.entity_description.set_fn(
            self.coordinator.device, ble_device, option
        )
        await self.coordinator.async_request_refresh()
