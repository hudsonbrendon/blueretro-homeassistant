"""High-level BlueRetro device operations over BLE."""

from __future__ import annotations

import logging

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from . import const
from .gameid import lookup_game_name
from .models import BlueRetroState
from .parser import decode_abi, decode_bdaddr, decode_string

_LOGGER = logging.getLogger(__name__)


class BlueRetroDevice:
    """Connects to a BlueRetro adapter to read state and send commands."""

    def __init__(self) -> None:
        self.last_state = BlueRetroState()

    async def _connect(self, ble_device: BLEDevice) -> BleakClient:
        return await establish_connection(
            BleakClient, ble_device, ble_device.address
        )

    async def async_update(self, ble_device: BLEDevice) -> BlueRetroState:
        """Connect, read all fields, disconnect. Never raises."""
        try:
            client = await self._connect(ble_device)
        except (BleakError, TimeoutError, OSError) as err:
            _LOGGER.debug("BlueRetro connect failed: %s", err)
            self.last_state = BlueRetroState(available=False)
            return self.last_state

        try:
            abi = decode_abi(await client.read_gatt_char(const.CHAR_ABI))
            fw = decode_string(await client.read_gatt_char(const.CHAR_APP))
            bdaddr = decode_bdaddr(await client.read_gatt_char(const.CHAR_BDADDR))
            game_id = decode_string(
                await self._command(client, const.CMD_GET_GAMEID)
            )
            cfg_src = decode_abi(
                await self._command(client, const.CMD_GET_CFG_SRC)
            )
        except (BleakError, TimeoutError, OSError, Exception) as err:  # noqa: BLE001
            _LOGGER.debug("BlueRetro read failed: %s", err)
            self.last_state = BlueRetroState(available=False)
            return self.last_state
        finally:
            await client.disconnect()

        state = BlueRetroState(
            available=True,
            fw_version=fw,
            abi_version=abi,
            bdaddr=bdaddr,
            game_id=game_id,
            cfg_src=cfg_src,
            game_name=lookup_game_name(game_id),
        )
        self.last_state = state
        return state

    async def _command(self, client: BleakClient, command: int) -> bytes:
        """Write a command byte to CHAR_CMD then read the response."""
        await client.write_gatt_char(const.CHAR_CMD, bytes([command]), response=True)
        return await client.read_gatt_char(const.CHAR_CMD)

    async def async_reboot(self, ble_device: BLEDevice) -> None:
        """Reboot the adapter."""
        await self._send_command(ble_device, const.CMD_SYS_RESET)

    async def async_deep_sleep(self, ble_device: BLEDevice) -> None:
        """Put the adapter into deep sleep."""
        await self._send_command(ble_device, const.CMD_SYS_DEEP_SLEEP)

    async def _send_command(self, ble_device: BLEDevice, command: int) -> None:
        client = await self._connect(ble_device)
        try:
            await client.write_gatt_char(
                const.CHAR_CMD, bytes([command]), response=True
            )
        finally:
            await client.disconnect()
