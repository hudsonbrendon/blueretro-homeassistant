"""BlueRetro buttons."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from homeassistant.components import persistent_notification
from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

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
    entities: list[ButtonEntity] = [
        BlueRetroButton(coordinator, desc) for desc in BUTTONS
    ]
    entities.append(BlueRetroBackupVmuButton(coordinator))
    async_add_entities(entities)


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


class BlueRetroBackupVmuButton(BlueRetroEntity, ButtonEntity):
    """Download the emulated Dreamcast VMU and save it as a .bin file."""

    _attr_translation_key = "backup_vmu"

    def __init__(self, coordinator: BlueRetroCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_backup_vmu"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        ble_device = self.coordinator.ble_device()
        if ble_device is None:
            raise HomeAssistantError(
                "BlueRetro is busy or out of range (only reachable when idle)"
            )
        data = await self.coordinator.device.async_read_vmu(ble_device)
        address = self.coordinator.address.replace(":", "")
        timestamp = dt_util.now().strftime("%Y%m%d_%H%M%S")
        path = self.hass.config.path(f"blueretro_vmu_{address}_{timestamp}.bin")
        await self.hass.async_add_executor_job(Path(path).write_bytes, data)
        persistent_notification.async_create(
            self.hass,
            f"Saved {len(data)} bytes to `{path}`.",
            title="BlueRetro VMU backup",
            notification_id=f"blueretro_vmu_backup_{address}",
        )
