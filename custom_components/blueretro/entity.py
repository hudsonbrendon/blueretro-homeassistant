"""Base entity for BlueRetro."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from blueretro_ble import parse_firmware
from .const import DOMAIN
from .coordinator import BlueRetroCoordinator


class BlueRetroEntity(CoordinatorEntity[BlueRetroCoordinator]):
    """Shared device info and availability."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BlueRetroCoordinator) -> None:
        super().__init__(coordinator)
        fw = coordinator.data.fw_version if coordinator.data else None
        sw_version, hw_version, platform = parse_firmware(fw)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={("bluetooth", coordinator.address)},
            name="BlueRetro",
            manufacturer="darthcloud",
            model=f"BlueRetro ({platform})" if platform else "BlueRetro",
            sw_version=sw_version,
            hw_version=hw_version,
        )

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.available
        )
