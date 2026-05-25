"""Parse the BlueRetro firmware string into device-info fields.

The adapter reports a firmware string like ``"v24.04 hw1 playstation"``. Split it
into a software version, a hardware revision, and a console/platform name so the
device page shows clean, structured fields instead of one opaque string.
"""

from __future__ import annotations


def parse_firmware(fw: str | None) -> tuple[str | None, str | None, str | None]:
    """Return ``(sw_version, hw_version, platform)`` parsed from ``fw``.

    Tolerant of unknown layouts: the first token is the version, any token
    starting with ``hw`` is the hardware revision, and the rest form the
    platform name (title-cased). Missing pieces come back as ``None``.
    """
    if not fw or not fw.strip():
        return (None, None, None)
    tokens = fw.split()
    version = tokens[0] or None
    hw_version = next(
        (t for t in tokens[1:] if t.lower().startswith("hw")), None
    )
    platform_tokens = [
        t for t in tokens[1:] if not t.lower().startswith("hw")
    ]
    platform = " ".join(platform_tokens).title() or None
    return (version, hw_version, platform)
