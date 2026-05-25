from blueretro_ble import const


def test_service_uuid():
    assert const.SERVICE_UUID == "56830f56-5180-fab0-314b-2fa176799a00"


def test_characteristic_uuids_share_service_prefix():
    prefix = "56830f56-5180-fab0-314b-2fa176799a"
    assert const.CHAR_ABI == prefix + "06"
    assert const.CHAR_CMD == prefix + "07"
    assert const.CHAR_APP == prefix + "09"
    assert const.CHAR_BDADDR == prefix + "0c"


def test_command_bytes():
    assert const.CMD_GET_GAMEID == 0x04
    assert const.CMD_GET_CFG_SRC == 0x05
    assert const.CMD_SYS_DEEP_SLEEP == 0x37
    assert const.CMD_SYS_RESET == 0x38
