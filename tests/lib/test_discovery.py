from dataclasses import dataclass, field

from blueretro_ble.const import SERVICE_UUID
from blueretro_ble.discovery import supports


@dataclass
class FakeInfo:
    name: str | None = None
    service_uuids: list[str] = field(default_factory=list)


def test_supports_name_and_service_uuid():
    info = FakeInfo(name="BlueRetro", service_uuids=[SERVICE_UUID])
    assert supports(info) is True


def test_supports_name_prefix_match():
    info = FakeInfo(name="BlueRetro_abcd", service_uuids=[SERVICE_UUID])
    assert supports(info) is True


def test_supports_name_only_still_true():
    # Some firmware advertises the name but not the service UUID.
    info = FakeInfo(name="BlueRetro_abcd", service_uuids=[])
    assert supports(info) is True


def test_supports_service_uuid_only_still_true():
    info = FakeInfo(name=None, service_uuids=[SERVICE_UUID])
    assert supports(info) is True


def test_supports_rejects_unrelated_device():
    info = FakeInfo(name="MyHeartRate", service_uuids=["0000180d-0000-1000-8000-00805f9b34fb"])
    assert supports(info) is False


def test_supports_rejects_empty():
    assert supports(FakeInfo()) is False
