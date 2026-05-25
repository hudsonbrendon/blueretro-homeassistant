import json
from pathlib import Path


def test_manifest_is_valid():
    path = Path("custom_components/blueretro/manifest.json")
    data = json.loads(path.read_text())
    assert data["domain"] == "blueretro"
    assert data["config_flow"] is True
    assert data["iot_class"] == "local_polling"
    assert "bluetooth_adapters" in data["dependencies"]
    assert data["bluetooth"] == [{"local_name": "BlueRetro*"}]
    assert any(r.startswith("blueretro-ble") for r in data["requirements"])
