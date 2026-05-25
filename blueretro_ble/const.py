"""BlueRetro BLE protocol constants (from darthcloud/BlueRetroWebCfg)."""

SERVICE_UUID = "56830f56-5180-fab0-314b-2fa176799a00"

# Directly readable characteristics
CHAR_ABI = "56830f56-5180-fab0-314b-2fa176799a06"
CHAR_CMD = "56830f56-5180-fab0-314b-2fa176799a07"
CHAR_APP = "56830f56-5180-fab0-314b-2fa176799a09"
CHAR_BDADDR = "56830f56-5180-fab0-314b-2fa176799a0c"

# Command bytes written to CHAR_CMD, response read back from CHAR_CMD
CMD_GET_GAMEID = 0x04
CMD_GET_CFG_SRC = 0x05
CMD_SYS_DEEP_SLEEP = 0x37
CMD_SYS_RESET = 0x38

# Advertised BLE name prefix used for discovery
NAME_PREFIX = "BlueRetro"
