"""BlueRetro buttons."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from blueretro_ble import BlueRetroDevice

from . import BlueRetroConfigEntry
from .coordinator import BlueRetroCoordinator
from .entity import BlueRetroEntity


@dataclass(frozen=True, kw_only=True)
class BlueRetroButtonDescription(ButtonEntityDescription):
    """Describes a BlueRetro button."""

    press_fn: Callable[[BlueRetroDevice, object], Awaitable[None]]


BUTTONS: tuple[BlueRetroButtonDescription, ...] = (
    BlueRetroButtonDescription(
        key="reboot",
        translation_key="reboot",
        press_fn=lambda device, ble: device.async_reboot(ble),
    ),
    BlueRetroButtonDescription(
        key="deep_sleep",
        translation_key="deep_sleep",
        press_fn=lambda device, ble: device.async_deep_sleep(ble),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlueRetroConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BlueRetro buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        BlueRetroButton(coordinator, desc) for desc in BUTTONS
    )


class BlueRetroButton(BlueRetroEntity, ButtonEntity):
    """A BlueRetro action button."""

    entity_description: BlueRetroButtonDescription

    def __init__(
        self,
        coordinator: BlueRetroCoordinator,
        description: BlueRetroButtonDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"

    @property
    def available(self) -> bool:
        # Buttons stay enabled so the user can attempt an action; the press
        # itself reports if the device is unreachable.
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        ble_device = self.coordinator.ble_device()
        if ble_device is None:
            raise HomeAssistantError(
                "BlueRetro is busy or out of range (only reachable when idle)"
            )
        await self.entity_description.press_fn(
            self.coordinator.device, ble_device
        )
