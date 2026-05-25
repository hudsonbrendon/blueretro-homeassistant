def test_public_exports():
    from blueretro_ble import (
        BlueRetroDevice,
        BlueRetroState,
        SERVICE_UUID,
        supports,
    )

    assert SERVICE_UUID.endswith("a00")
    assert callable(supports)
    assert BlueRetroDevice is not None
    assert BlueRetroState is not None
