"""Pure decoders for BlueRetro characteristic payloads."""

from __future__ import annotations


def decode_bdaddr(raw: bytes) -> str | None:
    """Decode a 6-byte BD address (little-endian, byte 5 first)."""
    if len(raw) < 6:
        return None
    return ":".join(f"{raw[i]:02x}" for i in range(5, -1, -1))


def decode_string(raw: bytes) -> str | None:
    """Decode a UTF-8 string, stripping trailing NULs. Empty -> None."""
    text = raw.decode("utf-8", errors="replace").rstrip("\x00").strip()
    return text or None


def decode_abi(raw: bytes) -> int | None:
    """Decode a small integer carried in the first byte."""
    if not raw:
        return None
    return raw[0]
