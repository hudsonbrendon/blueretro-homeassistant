"""BlueRetro firmware update entity.

Surfaces whether a newer BlueRetro firmware release exists on GitHub. It does
*not* install: BlueRetro's over-the-air update is not yet implemented in the
``blueretro-ble`` library, so this entity is detection-only and points the user
at the release page.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta

from homeassistant.components.update import UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from blueretro_ble import parse_firmware

from . import BlueRetroConfigEntry
from .coordinator import BlueRetroCoordinator
from .entity import BlueRetroEntity

_LOGGER = logging.getLogger(__name__)

GITHUB_LATEST_RELEASE = (
    "https://api.github.com/repos/darthcloud/BlueRetro/releases/latest"
)
# GitHub's release feed barely moves; check sparingly to stay a good citizen.
MIN_FETCH_INTERVAL = timedelta(hours=6)

# Pull the first dotted version token (e.g. "1.8.1") out of a firmware string
# like "v1.8.1_master_dc_0c5d35d" or a release tag like "v1.8".
_VERSION_RE = re.compile(r"(\d+\.\d+(?:\.\d+)?)")


def _semver(raw: str | None) -> str | None:
    """Return the dotted version token from a raw firmware/tag string."""
    if not raw:
        return None
    match = _VERSION_RE.search(raw)
    return match.group(1) if match else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlueRetroConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BlueRetro firmware update entity."""
    async_add_entities([BlueRetroFirmwareUpdate(entry.runtime_data)])


class BlueRetroFirmwareUpdate(BlueRetroEntity, UpdateEntity):
    """Detection-only firmware update for the BlueRetro adapter."""

    _attr_translation_key = "firmware"
    _attr_should_poll = True

    def __init__(self, coordinator: BlueRetroCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_firmware_update"
        self._latest_version: str | None = None
        self._release_url: str | None = None

    @property
    def installed_version(self) -> str | None:
        if self.coordinator.data is None:
            return None
        sw_version, _, _ = parse_firmware(self.coordinator.data.fw_version)
        return _semver(sw_version)

    @property
    def latest_version(self) -> str | None:
        # Never report an "update" we can't trust: if we have no latest yet, or
        # the installed version is unknown, mirror the installed value so Home
        # Assistant shows no pending update.
        if self._latest_version is None:
            return self.installed_version
        return self._latest_version

    @property
    def release_url(self) -> str | None:
        return self._release_url

    @Throttle(MIN_FETCH_INTERVAL)
    async def _async_fetch_latest(self) -> None:
        """Read the latest release tag from GitHub (throttled)."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(GITHUB_LATEST_RELEASE) as resp:
                if resp.status != 200:
                    _LOGGER.debug(
                        "GitHub release check returned HTTP %s", resp.status
                    )
                    return
                payload = await resp.json()
        except Exception as err:  # noqa: BLE001 - best-effort network check
            _LOGGER.debug("GitHub release check failed: %s", err)
            return
        self._latest_version = _semver(payload.get("tag_name"))
        self._release_url = payload.get("html_url")

    async def async_update(self) -> None:
        await self._async_fetch_latest()
