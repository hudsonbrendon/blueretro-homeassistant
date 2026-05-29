"""Constants for the BlueRetro integration."""

DOMAIN = "blueretro"

# Default poll cadence (minutes); overridable per entry via the options flow.
DEFAULT_SCAN_INTERVAL_MINUTES = 5

# Options-flow keys.
CONF_SCAN_INTERVAL = "scan_interval"
MIN_SCAN_INTERVAL_MINUTES = 1
MAX_SCAN_INTERVAL_MINUTES = 60
