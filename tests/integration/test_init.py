from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from blueretro_ble import BlueRetroState
from custom_components.blueretro.const import DOMAIN


async def test_setup_and_unload_entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="BlueRetro", unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)

    state = BlueRetroState(available=True, fw_version="v1.8.1")
    with (
        patch(
            "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_update",
            AsyncMock(return_value=state),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_device_named_from_advertisement(hass):
    from unittest.mock import MagicMock

    from homeassistant.helpers import device_registry as dr

    entry = MockConfigEntry(domain=DOMAIN, title="BlueRetro", unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)
    info = MagicMock()
    info.name = "BlueRetro_DC_2A6E"
    info.rssi = -50
    with (
        patch(
            "custom_components.blueretro.coordinator.bluetooth.async_last_service_info",
            return_value=info,
        ),
        patch(
            "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_update",
            AsyncMock(return_value=BlueRetroState(available=True)),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, "AA:BB:CC:DD:EE:FF")}
    )
    assert device.name == "BlueRetro_DC_2A6E"
    assert hass.states.get("sensor.blueretro_dc_2a6e_signal_strength") is None  # disabled by default
    assert hass.states.get("binary_sensor.blueretro_dc_2a6e_controller_connected").state == "off"


async def test_device_renamed_on_first_advertisement(hass):
    from unittest.mock import MagicMock

    from homeassistant.helpers import device_registry as dr

    entry = MockConfigEntry(domain=DOMAIN, title="BlueRetro", unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_update",
            AsyncMock(return_value=BlueRetroState(available=True)),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    info = MagicMock(); info.name = "BlueRetro_GC_106E"; info.rssi = -40
    entry.runtime_data._async_seen(info, None)
    await hass.async_block_till_done()
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "AA:BB:CC:DD:EE:FF")})
    assert device.name == "BlueRetro_GC_106E"


async def test_device_named_from_entry_title_when_not_advertising(hass):
    from homeassistant.helpers import device_registry as dr

    entry = MockConfigEntry(
        domain=DOMAIN, title="BlueRetro_N64_8756", unique_id="AA:BB:CC:DD:EE:FF", data={}
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_update",
            AsyncMock(return_value=BlueRetroState(available=False)),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, "AA:BB:CC:DD:EE:FF")}
    )
    assert device.name == "BlueRetro_N64_8756"


async def test_orphan_config_source_sensor_removed(hass):
    from homeassistant.helpers import entity_registry as er

    entry = MockConfigEntry(domain=DOMAIN, title="BlueRetro", unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)
    reg = er.async_get(hass)
    reg.async_get_or_create(
        "sensor", DOMAIN, "AA:BB:CC:DD:EE:FF_config_source", config_entry=entry
    )
    with (
        patch(
            "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_update",
            AsyncMock(return_value=BlueRetroState(available=True)),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert reg.async_get_entity_id("sensor", DOMAIN, "AA:BB:CC:DD:EE:FF_config_source") is None


async def test_setup_does_not_block_on_slow_ble(hass):
    """A hung first connect must not fail/cancel entry setup (boot timeout)."""
    import asyncio

    entry = MockConfigEntry(domain=DOMAIN, title="BlueRetro", unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)
    hang = asyncio.Event()

    async def slow_update(*args, **kwargs):
        await hang.wait()
        return BlueRetroState(available=True, fw_version="v25.04")

    with (
        patch(
            "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_update",
            slow_update,
        ),
    ):
        assert await asyncio.wait_for(
            hass.config_entries.async_setup(entry.entry_id), 5
        )
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert hass.states.get("sensor.blueretro_firmware").state == "unavailable"
        hang.set()
        await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("sensor.blueretro_firmware").state == "v25.04"


async def test_poll_timeout_marks_unavailable_with_reason(hass):
    import asyncio

    from custom_components.blueretro import coordinator as coord_mod

    entry = MockConfigEntry(domain=DOMAIN, title="BlueRetro", unique_id="AA:BB:CC:DD:EE:FF", data={})
    entry.add_to_hass(hass)

    async def never(*args, **kwargs):
        await asyncio.sleep(3600)

    with (
        patch.object(coord_mod, "POLL_TIMEOUT", 0.01),
        patch(
            "custom_components.blueretro.coordinator.bluetooth.async_ble_device_from_address",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.blueretro.coordinator.BlueRetroDevice.async_update",
            never,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("binary_sensor.blueretro_config_available")
    assert state.state == "off"
    assert "longer than" in state.attributes["reason"]
