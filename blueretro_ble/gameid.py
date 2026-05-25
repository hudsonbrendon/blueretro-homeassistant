"""Resolve a BlueRetro Game ID to a human-readable game name."""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path


def _bundled_db_path() -> Path:
    return Path(str(resources.files("blueretro_ble") / "gameid.db"))


def lookup_game_name(game_id: str | None, db_path: Path | None = None) -> str | None:
    """Look up a game name in the SQLite game database.

    Returns None for unknown IDs, missing DB, or any read error.
    """
    if not game_id:
        return None
    path = db_path or _bundled_db_path()
    if not Path(path).exists():
        return None
    try:
        uri = f"file:{path}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            row = conn.execute(
                "SELECT name FROM games WHERE id = ? LIMIT 1", (game_id,)
            ).fetchone()
    except sqlite3.Error:
        return None
    return row[0] if row else None
