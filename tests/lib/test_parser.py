from blueretro_ble.parser import decode_abi, decode_bdaddr, decode_string


def test_decode_bdaddr_reverses_byte_order():
    raw = bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
    assert decode_bdaddr(raw) == "66:55:44:33:22:11"


def test_decode_bdaddr_pads_single_hex_digits():
    raw = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x0a])
    assert decode_bdaddr(raw) == "0a:05:04:03:02:01"


def test_decode_bdaddr_too_short_returns_none():
    assert decode_bdaddr(bytes([0x01, 0x02])) is None


def test_decode_string_utf8():
    assert decode_string(b"v1.8.1") == "v1.8.1"


def test_decode_string_strips_trailing_nulls():
    assert decode_string(b"abc\x00\x00") == "abc"


def test_decode_string_empty_returns_none():
    assert decode_string(b"") is None


def test_decode_abi_first_byte():
    assert decode_abi(bytes([0x02, 0x00])) == 2


def test_decode_abi_empty_returns_none():
    assert decode_abi(b"") is None
