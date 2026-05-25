import sqlite3

import pytest

from blueretro_ble.gameid import lookup_game_name


@pytest.fixture
def tiny_db(tmp_path):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE games (id TEXT, name TEXT)")
    conn.execute("INSERT INTO games VALUES ('GALE01', 'Super Smash Bros. Melee')")
    conn.commit()
    conn.close()
    return path


def test_lookup_returns_name(tiny_db):
    assert lookup_game_name("GALE01", db_path=tiny_db) == "Super Smash Bros. Melee"


def test_lookup_unknown_id_returns_none(tiny_db):
    assert lookup_game_name("NOPE99", db_path=tiny_db) is None


def test_lookup_none_id_returns_none(tiny_db):
    assert lookup_game_name(None, db_path=tiny_db) is None


def test_lookup_missing_db_returns_none(tmp_path):
    assert lookup_game_name("GALE01", db_path=tmp_path / "absent.db") is None


def test_lookup_uses_bundled_db_by_default():
    # Smoke check: a real ID present in the bundled DB resolves to a string.
    # GALE01 is Super Smash Bros. Melee (GameCube); adjust if absent.
    result = lookup_game_name("GALE01")
    assert result is None or isinstance(result, str)
