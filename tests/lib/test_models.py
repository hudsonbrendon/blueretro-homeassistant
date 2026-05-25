from blueretro_ble.models import BlueRetroState


def test_default_state_is_unavailable_with_no_data():
    state = BlueRetroState()
    assert state.available is False
    assert state.fw_version is None
    assert state.abi_version is None
    assert state.bdaddr is None
    assert state.game_id is None
    assert state.game_name is None
    assert state.cfg_src is None


def test_state_accepts_values():
    state = BlueRetroState(
        available=True,
        fw_version="v1.8.1",
        abi_version=2,
        bdaddr="66:55:44:33:22:11",
        game_id="GALE01",
        game_name="Super Smash Bros. Melee",
        cfg_src=1,
    )
    assert state.available is True
    assert state.game_name == "Super Smash Bros. Melee"
