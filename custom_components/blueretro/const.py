"""Constants for the BlueRetro integration."""

DOMAIN = "blueretro"

# Default poll cadence (minutes); overridable per entry via the options flow.
DEFAULT_SCAN_INTERVAL_MINUTES = 5

# Options-flow keys.
CONF_SCAN_INTERVAL = "scan_interval"
MIN_SCAN_INTERVAL_MINUTES = 1
MAX_SCAN_INTERVAL_MINUTES = 60

# How many output ports to read/expose (multitap). 1 = single controller; raise
# for multitap setups. Upper bound mirrors blueretro_ble.const.MAX_OUTPUT (12).
CONF_OUTPUT_PORTS = "output_ports"
DEFAULT_OUTPUT_PORTS = 1
MAX_OUTPUT_PORTS = 12
