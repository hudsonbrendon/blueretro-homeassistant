"""Diagnostics support for BlueRetro."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BlueRetroConfigEntry

TO_REDACT = {"unique_id", "bdaddr", "address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BlueRetroConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "last_update_success": coordinator.last_update_success,
            "last_error": coordinator.last_error,
            "output_ports": coordinator.output_ports,
            "state": asdict(coordinator.data) if coordinator.data else None,
        },
        TO_REDACT,
    )
