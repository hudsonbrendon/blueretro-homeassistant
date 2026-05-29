"""BlueRetro selects (per-output device mode and accessory)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from blueretro_ble import (
    ACCESSORY_CFG,
    DEVICE_CFG,
    INQUIRY_MODE,
    MULTITAP_CFG,
    SYSTEM_CFG,
    BlueRetroDevice,
    BlueRetroState,
)

from . import BlueRetroConfigEntry
from .coordinator import BlueRetroCoordinator
from .entity import BlueRetroEntity


@dataclass(frozen=True, kw_only=True)
class BlueRetroSelectDescription(SelectEntityDescription):
    """Describes a BlueRetro select."""

    current_fn: Callable[[BlueRetroState], str | None]
    set_fn: Callable[[BlueRetroDevice, object, str], Awaitable[None]]
    placeholders: dict[str, str] | None = None


def _output_selects(ports: int) -> list[BlueRetroSelectDescription]:
    """Build per-port controller-mode + accessory selects for ``ports`` ports.

    Port 0 keeps the original ``controller_mode`` / ``accessory`` keys (stable
    entity IDs); higher ports get ``*_port{N}`` keys with a localized
    ``(port N)`` suffix.
    """
    descs: list[BlueRetroSelectDescription] = []
    for port in range(ports):
        suffix = "" if port == 0 else f"_port{port + 1}"
        placeholders = None if port == 0 else {"port": str(port + 1)}
        descs.append(
            BlueRetroSelectDescription(
                key=f"controller_mode{suffix}",
                translation_key=(
                    "controller_mode" if port == 0 else "controller_mode_port"
                ),
                placeholders=placeholders,
                options=list(DEVICE_CFG),
                current_fn=lambda s, p=port: _port_value(s, p)[0],
                set_fn=lambda device, ble, opt, p=port: (
                    device.async_set_output_config(ble, p, device=opt)
                ),
            )
        )
        descs.append(
            BlueRetroSelectDescription(
                key=f"accessory{suffix}",
                translation_key=(
                    "accessory" if port == 0 else "accessory_port"
                ),
                placeholders=placeholders,
                options=list(ACCESSORY_CFG),
                current_fn=lambda s, p=port: _port_value(s, p)[1],
                set_fn=lambda device, ble, opt, p=port: (
                    device.async_set_output_config(ble, p, accessory=opt)
                ),
            )
        )
    return descs


def _port_value(
    state: BlueRetroState, port: int
) -> tuple[str | None, str | None]:
    """Return ``(device, accessory)`` for a port.

    Prefers ``state.ports``; for port 0 falls back to the legacy
    ``controller_mode`` / ``accessory`` mirror when ``ports`` is empty.
    """
    if port in state.ports:
        return state.ports[port]
    if port == 0:
        return (state.controller_mode, state.accessory)
    return (None, None)


GLOBAL_SELECTS: tuple[BlueRetroSelectDescription, ...] = (
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
    BlueRetroSelectDescription(
        key="multitap",
        translation_key="multitap",
        options=list(MULTITAP_CFG),
        current_fn=lambda s: s.multitap,
        # Global-config write; reboots the adapter to apply.
        set_fn=lambda device, ble, opt: device.async_set_global_config(
            ble, multitap=opt
        ),
    ),
    BlueRetroSelectDescription(
        key="system",
        translation_key="system",
        options=list(SYSTEM_CFG),
        current_fn=lambda s: s.system,
        set_fn=lambda device, ble, opt: device.async_set_global_config(
            ble, system=opt
        ),
    ),
    BlueRetroSelectDescription(
        key="inquiry_mode",
        translation_key="inquiry_mode",
        options=list(INQUIRY_MODE),
        current_fn=lambda s: s.inquiry_mode,
        set_fn=lambda device, ble, opt: device.async_set_global_config(
            ble, inquiry_mode=opt
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlueRetroConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BlueRetro selects (per-port output config + global config)."""
    coordinator = entry.runtime_data
    descriptions = _output_selects(coordinator.output_ports) + list(
        GLOBAL_SELECTS
    )
    async_add_entities(
        BlueRetroSelect(coordinator, desc) for desc in descriptions
    )


class BlueRetroSelect(BlueRetroEntity, SelectEntity):
    """A BlueRetro output-config or global-config select."""

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
        if description.placeholders:
            self._attr_translation_placeholders = description.placeholders

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
