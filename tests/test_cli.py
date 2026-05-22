from __future__ import annotations

import subprocess

import numpy as np
import pytest

from posture_guard.cli import (
    ConsequenceAction,
    ConsequenceController,
    PostureWarningPopup,
    WifiController,
    build_profile,
    consequence_action_from_trackbar,
    consequence_command,
    consequence_commands,
    consequence_timer_line,
    deviation_score,
    discover_wifi_device,
    initial_consequence_action_value,
    is_deviation_entry,
    initial_trackbar_value,
    posture_features,
    should_run_consequence,
    trackbar_seconds,
    warning_popup_command,
    wifi_power_command,
    wifi_power_is_on,
    wifi_set_power_command,
)


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_discover_wifi_device_finds_device(monkeypatch: pytest.MonkeyPatch) -> None:
    output = """
Hardware Port: Ethernet Adapter
Device: en4

Hardware Port: Wi-Fi
Device: en0
Ethernet Address: aa:bb:cc:dd:ee:ff
"""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed(stdout=output))

    assert discover_wifi_device("darwin") == "en0"


def test_discover_wifi_device_finds_windows_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return completed(stdout="Wi-Fi\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert discover_wifi_device("win32") == "Wi-Fi"
    assert calls[0][:4] == ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass"]


def test_mediapipe_solutions_pose_is_available() -> None:
    import mediapipe as mp

    assert mp.solutions.pose.Pose is not None


def test_trackbar_seconds_enforces_minimum() -> None:
    assert trackbar_seconds(0) == 1.0
    assert trackbar_seconds(7) == 7.0


def test_initial_trackbar_value_stays_within_supported_range() -> None:
    assert initial_trackbar_value(0) == 1
    assert initial_trackbar_value(30) == 30
    assert initial_trackbar_value(90) == 60


def landmark(x: float, y: float, visibility: float = 1.0) -> object:
    from types import SimpleNamespace

    return SimpleNamespace(x=x, y=y, visibility=visibility)


def pose_landmarks(
    *,
    nose: tuple[float, float] = (0.50, 0.30),
    left_shoulder: tuple[float, float] = (0.40, 0.60),
    right_shoulder: tuple[float, float] = (0.60, 0.60),
    left_ear: tuple[float, float] = (0.45, 0.32),
    right_ear: tuple[float, float] = (0.55, 0.32),
) -> list[object]:
    import mediapipe as mp

    landmarks = [landmark(0.0, 0.0, visibility=0.0) for _ in range(33)]
    pose = mp.solutions.pose.PoseLandmark
    landmarks[pose.NOSE.value] = landmark(*nose)
    landmarks[pose.LEFT_SHOULDER.value] = landmark(*left_shoulder)
    landmarks[pose.RIGHT_SHOULDER.value] = landmark(*right_shoulder)
    landmarks[pose.LEFT_EAR.value] = landmark(*left_ear)
    landmarks[pose.RIGHT_EAR.value] = landmark(*right_ear)
    return landmarks


def test_posture_features_include_weighted_shoulder_position() -> None:
    reference = posture_features(pose_landmarks())
    shifted = posture_features(
        pose_landmarks(
            nose=(0.50, 0.40),
            left_shoulder=(0.40, 0.70),
            right_shoulder=(0.60, 0.70),
            left_ear=(0.45, 0.42),
            right_ear=(0.55, 0.42),
        )
    )

    assert reference is not None
    assert shifted is not None
    assert shifted[1] > reference[1]


def test_discover_wifi_device_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed(stdout="Hardware Port: Ethernet\n"))

    with pytest.raises(RuntimeError, match="Could not discover"):
        discover_wifi_device("darwin")


def test_discover_wifi_device_raises_when_windows_adapter_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed(stderr="not found", returncode=2))

    with pytest.raises(RuntimeError, match="not found"):
        discover_wifi_device("win32")


def test_wifi_controller_dry_run_does_not_call_networksetup(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    WifiController(device="en0", dry_run=True, os_name="darwin").turn_off()

    assert calls == []


def test_wifi_controller_turn_off_runs_networksetup(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command == ["networksetup", "-getairportpower", "en0"]:
            return completed(stdout="Wi-Fi Power (en0): Off\n")
        return completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    WifiController(device="en0", dry_run=False, os_name="darwin").turn_off()

    assert calls == [
        ["networksetup", "-setairportpower", "en0", "off"],
        ["networksetup", "-getairportpower", "en0"],
    ]


def test_wifi_controller_turn_off_raises_when_wifi_stays_on(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command == ["networksetup", "-getairportpower", "en0"]:
            return completed(stdout="Wi-Fi Power (en0): On\n")
        return completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="still reported as On"):
        WifiController(device="en0", dry_run=False, os_name="darwin").turn_off()


def test_wifi_controller_turn_on_runs_networksetup(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    WifiController(device="en0", dry_run=False, os_name="darwin").turn_on()

    assert calls == [["networksetup", "-setairportpower", "en0", "on"]]


def test_wifi_controller_is_on_parses_airport_power(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed(stdout="Wi-Fi Power (en0): On\n"))

    assert WifiController(device="en0", dry_run=False, os_name="darwin").is_on() is True


def test_wifi_controller_turn_off_runs_windows_powershell(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if "Get-NetAdapter" in command[-1]:
            return completed(stdout="Off\n")
        return completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    WifiController(device="Wi-Fi", dry_run=False, os_name="win32").turn_off()

    assert calls[0][:4] == ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass"]
    assert "Disable-NetAdapter -Name 'Wi-Fi' -Confirm:$false" in calls[0][-1]
    assert "Get-NetAdapter -Name 'Wi-Fi'" in calls[1][-1]


def test_wifi_power_commands_support_windows() -> None:
    assert "Get-NetAdapter -Name 'Wi-Fi'" in wifi_power_command("Wi-Fi", "win32")[-1]
    assert "Enable-NetAdapter -Name 'Wi-Fi' -Confirm:$false" in wifi_set_power_command("Wi-Fi", True, "win32")[-1]
    assert "Disable-NetAdapter -Name 'Wi-Fi' -Confirm:$false" in wifi_set_power_command("Wi-Fi", False, "win32")[-1]
    assert wifi_power_is_on("On\n", "win32") is True
    assert wifi_power_is_on("Off\n", "win32") is False


def test_warning_popup_opens_once_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    popen_calls: list[list[str]] = []

    class FakeProcess:
        terminated = False

        def poll(self) -> int | None:
            return None if not self.terminated else 0

        def terminate(self) -> None:
            self.terminated = True

    fake_process = FakeProcess()

    def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
        popen_calls.append(command)
        return fake_process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    popup = PostureWarningPopup(os_name="darwin")
    popup.show_count_started()
    popup.show_count_started()

    assert len(popen_calls) == 1
    assert popen_calls[0][0] == "osascript"
    assert popup.is_open() is True

    popup.close()

    assert fake_process.terminated is True
    assert popup.is_open() is False


def test_warning_popup_tracks_user_dismissal(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProcess:
        def poll(self) -> int:
            return 0

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    popup = PostureWarningPopup(os_name="darwin")
    popup.show_count_started()

    assert popup.is_open() is False


def test_consequence_controller_dry_run_does_not_call_command(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    ConsequenceController(action=ConsequenceAction.LOCK, dry_run=True, os_name="darwin").run()

    assert calls == []


def test_consequence_controller_runs_selected_command(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    ConsequenceController(action=ConsequenceAction.LOCK, dry_run=False, os_name="darwin").run()

    assert calls == [consequence_command(ConsequenceAction.LOCK, "darwin")]


def test_consequence_command_supports_lock_and_reboot() -> None:
    lock_commands = consequence_commands(ConsequenceAction.LOCK, "darwin")
    assert lock_commands[0] == ["/usr/bin/pmset", "displaysleepnow"]
    assert lock_commands[-1] == [
        "osascript",
        "-e",
        'tell application "System Events" to key code 12 using {control down, command down}',
    ]
    assert consequence_command(ConsequenceAction.REBOOT, "darwin") == [
        "osascript",
        "-e",
        'tell application "System Events" to restart',
    ]


def test_consequence_command_supports_windows_lock_and_reboot() -> None:
    assert consequence_commands(ConsequenceAction.LOCK, "win32") == [["rundll32.exe", "user32.dll,LockWorkStation"]]
    assert consequence_command(ConsequenceAction.REBOOT, "win32") == ["shutdown", "/r", "/t", "0"]


def test_warning_popup_command_supports_mac_and_windows() -> None:
    mac_command = warning_popup_command("darwin")
    windows_command = warning_popup_command("win32")

    assert mac_command[0] == "osascript"
    assert "display dialog" in mac_command[-1]
    assert windows_command[:4] == ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass"]
    assert "MessageBox" in windows_command[-1]


def test_consequence_timer_line_shows_remaining_seconds() -> None:
    assert consequence_timer_line(
        now=100.0,
        warning_started_at=None,
        consequence_grace_seconds=60.0,
        action=ConsequenceAction.LOCK,
    ) is None
    assert consequence_timer_line(
        now=115.2,
        warning_started_at=100.0,
        consequence_grace_seconds=60.0,
        action=ConsequenceAction.LOCK,
    ) == "Lock timer: 45s"
    assert consequence_timer_line(
        now=175.0,
        warning_started_at=100.0,
        consequence_grace_seconds=60.0,
        action=ConsequenceAction.REBOOT,
    ) == "Reboot timer: 0s"
    assert consequence_timer_line(
        now=115.0,
        warning_started_at=100.0,
        consequence_grace_seconds=60.0,
        action=ConsequenceAction.NONE,
    ) is None


def test_should_run_consequence_respects_popup_setting() -> None:
    assert should_run_consequence(
        now=120.0,
        warning_started_at=100.0,
        consequence_grace_seconds=30.0,
        popup_enabled=False,
        popup_open=False,
    ) is False
    assert should_run_consequence(
        now=130.0,
        warning_started_at=100.0,
        consequence_grace_seconds=30.0,
        popup_enabled=False,
        popup_open=False,
    ) is True
    assert should_run_consequence(
        now=130.0,
        warning_started_at=100.0,
        consequence_grace_seconds=30.0,
        popup_enabled=True,
        popup_open=False,
    ) is False
    assert should_run_consequence(
        now=130.0,
        warning_started_at=100.0,
        consequence_grace_seconds=30.0,
        popup_enabled=True,
        popup_open=True,
    ) is True


def test_consequence_action_trackbar_mapping() -> None:
    assert consequence_action_from_trackbar(0) is ConsequenceAction.LOCK
    assert consequence_action_from_trackbar(1) is ConsequenceAction.REBOOT
    assert consequence_action_from_trackbar(2) is ConsequenceAction.NONE
    assert consequence_action_from_trackbar(99) is ConsequenceAction.NONE
    assert initial_consequence_action_value(ConsequenceAction.REBOOT) == 1


def test_build_profile_creates_threshold_and_scores_reference_low() -> None:
    samples = [np.array([1.0, 2.0, 3.0, 4.0, 0.0]) + (index % 3) * 0.01 for index in range(45)]

    profile = build_profile(samples)

    assert profile.threshold >= 2.0
    assert deviation_score(np.array([1.01, 2.01, 3.01, 4.01, 0.01]), profile) < profile.threshold


def test_deviation_score_increases_for_large_drift() -> None:
    samples = [np.array([0.0, 0.0, 0.0, 0.0, 0.0]) + (index % 2) * 0.01 for index in range(40)]
    profile = build_profile(samples)

    assert deviation_score(np.array([0.5, 0.5, 0.5, 0.5, 0.5]), profile) > profile.threshold


def test_deviation_entry_requires_margin_above_threshold() -> None:
    profile = build_profile([np.array([0.0, 0.0, 0.0, 0.0, 0.0]) + (index % 2) * 0.01 for index in range(40)])

    assert is_deviation_entry(profile.threshold + 0.01, profile, margin_ratio=0.15) is False
    assert is_deviation_entry(profile.threshold * 1.15, profile, margin_ratio=0.15) is True
