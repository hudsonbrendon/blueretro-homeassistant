"""Shared fixtures enabling custom integrations in HA tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom_components/ in every HA test."""
    yield
