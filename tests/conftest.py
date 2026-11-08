import os

import pytest


@pytest.fixture(autouse=True)
def _offline_fx(monkeypatch):
    """The suite must not depend on the ECB being reachable; fx tests switch the feed on explicitly."""
    monkeypatch.setenv("FX_FEED", "off")
    yield
