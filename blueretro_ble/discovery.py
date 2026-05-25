"""Detect a BlueRetro device from its BLE advertisement."""

from __future__ import annotations

from typing import Protocol

from .const import NAME_PREFIX, SERVICE_UUID


class _AdvertisementLike(Protocol):
    name: str | None
    service_uuids: list[str]


def supports(info: _AdvertisementLike) -> bool:
    """True if the advertisement looks like a BlueRetro adapter."""
    name = info.name or ""
    if name.startswith(NAME_PREFIX):
        return True
    return SERVICE_UUID.lower() in {u.lower() for u in info.service_uuids}
