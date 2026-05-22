from __future__ import annotations

import os
import time

import pytest

from posture_guard.cli import WifiController


pytestmark = pytest.mark.skipif(
    os.environ.get("POSTURE_GUARD_RUN_WIFI_INTEGRATION") != "1",
    reason="Set POSTURE_GUARD_RUN_WIFI_INTEGRATION=1 to run real Wi-Fi power integration tests.",
)


def wait_until_wifi(controller: WifiController, expected_on: bool, timeout_seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if controller.is_on() is expected_on:
            return True
        time.sleep(0.5)
    return controller.is_on() is expected_on


def test_wifi_turns_off_then_back_on() -> None:
    wifi = WifiController(device="en0", dry_run=False)

    try:
        wifi.turn_on()
        assert wait_until_wifi(wifi, True)

        wifi.turn_off()
        assert wait_until_wifi(wifi, False)
    finally:
        wifi.turn_on()

    assert wait_until_wifi(wifi, True)
