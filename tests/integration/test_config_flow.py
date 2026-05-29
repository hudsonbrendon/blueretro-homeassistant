from unittest.mock import patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import SOURCE_BLUETOOTH
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from blueretro_ble.const import SERVICE_UUID
from custom_components.blueretro.const import (
    CONF_OUTPUT_PORTS,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

ADDRESS = "AA:BB:CC:DD:EE:FF"


def _service_info(
    name: str = "BlueRetro_abcd", service_uuids: list[str] | None = None
) -> BluetoothServiceInfoBleak:
    """Build a BluetoothServiceInfoBleak directly.

    The HA test helpers ``generate_ble_device``/``generate_advertisement_data``
    are not exported by the installed pytest-homeassistant-custom-component, and
    ``from_advertisement`` is broken for the Bleak subclass in this version, so
    construct the object directly with all required fields.
    """
    uuids = [SERVICE_UUID] if service_uuids is None else service_uuids
    device = BLEDevice(ADDRESS, name, {})
    adv = AdvertisementData(
        local_name=name,
        manufacturer_data={},
        service_data={},
        service_uuids=uuids,
        tx_power=-127,
        rssi=-60,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak(
        name, ADDRESS, -60, {}, {}, uuids, "local", device, adv, True, 0.0, -127
    )


async def test_bluetooth_discovery_creates_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=_service_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(
        "custom_components.blueretro.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "BlueRetro_abcd"
    assert result2["result"].unique_id == ADDRESS


async def test_bluetooth_discovery_rejects_non_blueretro(hass):
    info = _service_info(name="RandomThing", service_uuids=[])
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_options_flow_sets_scan_interval(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={})
    entry.add_to_hass(hass)
    # Patch the integration setup so the options flow can be exercised without
    # bringing up the BLE coordinator.
    with patch(
        "custom_components.blueretro.async_setup_entry", return_value=True
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_SCAN_INTERVAL: 10, CONF_OUTPUT_PORTS: 4},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 10
    assert entry.options[CONF_OUTPUT_PORTS] == 4
