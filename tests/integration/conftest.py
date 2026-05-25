"""Fixtures for BlueRetro integration tests.

The integration depends on ``bluetooth_adapters`` (and thus ``bluetooth``), so
every integration test needs the bluetooth stack mocked and set up. The
``enable_bluetooth`` fixture from pytest-homeassistant-custom-component mocks the
adapters and scanner, sets up a bluetooth config entry, and unloads it on
teardown (which cancels the manager's unavailable-check timer).

On non-Linux hosts the plugin's adapter mock forces ``platform.system`` to
"Linux" but leaves ``LinuxAdapters.history`` unpatched; that property reaches
into dbus and crashes here, so we patch it to an empty history. The patch must
be active *before* ``enable_bluetooth`` sets bluetooth up, hence the explicit
fixture ordering.
"""

from unittest.mock import PropertyMock, patch

import pytest


@pytest.fixture(autouse=True)
def patch_adapter_history():
    """Return an empty local adapter history so bluetooth setup avoids dbus."""
    with patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.history",
        new_callable=PropertyMock,
        return_value={},
    ):
        yield


@pytest.fixture
def expected_lingering_timers() -> bool:
    """Allow the bluetooth scanner's device-expiry timer to linger.

    Setting up the real ``bluetooth`` integration (a hard dependency of
    ``bluetooth_adapters``) starts a scanner whose periodic expiry timer is not
    cleaned up under the mocked macOS test harness. This is harness noise, not a
    leak in the BlueRetro integration, so we downgrade it from a failure to a
    warning the same way Home Assistant core does for such components.
    """
    return True


@pytest.fixture(autouse=True)
def auto_enable_bluetooth(patch_adapter_history, enable_bluetooth):
    """Mock and set up the bluetooth stack for every integration test."""
    yield
