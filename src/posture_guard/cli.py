from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from subprocess import Popen
from typing import Iterable

import numpy as np


class MonitorState(Enum):
    READY = "ready"
    CALIBRATING = "calibrating"
    MONITORING = "monitoring"
    WAITING_MANUAL_RECOVERY = "waiting_manual_recovery"


class ConsequenceAction(Enum):
    LOCK = "lock"
    REBOOT = "reboot"
    NONE = "none"


@dataclass(frozen=True)
class CalibrationProfile:
    mean: np.ndarray
    scale: np.ndarray
    threshold: float


@dataclass(frozen=True)
class MonitorSettings:
    calibration_seconds: float
    deviation_seconds: float
    wifi_off_enabled: bool
    consequence_action: ConsequenceAction
    consequence_grace_seconds: float
    popup_enabled: bool


@dataclass(frozen=True)
class WifiController:
    device: str
    dry_run: bool

    @classmethod
    def create(cls, device: str, dry_run: bool) -> "WifiController":
        return cls(device=discover_wifi_device() if device == "auto" else device, dry_run=dry_run)

    def is_on(self) -> bool:
        result = subprocess.run(
            ["networksetup", "-getairportpower", self.device],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return "On" in result.stdout

    def turn_off(self) -> None:
        command = ["networksetup", "-setairportpower", self.device, "off"]
        if self.dry_run:
            print(f"[dry-run] would run: {' '.join(command)}")
            return

        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())

        if self.is_on():
            raise RuntimeError("Wi-Fi off command completed, but Wi-Fi is still reported as On.")

    def turn_on(self) -> None:
        command = ["networksetup", "-setairportpower", self.device, "on"]
        if self.dry_run:
            print(f"[dry-run] would run: {' '.join(command)}")
            return

        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())


@dataclass
class PostureWarningPopup:
    process: Popen[str] | None = None

    def show_count_started(self) -> None:
        if self.is_open():
            return

        script = (
            'display dialog "姿勢の崩れを検知しました。タイマーが終わる前に姿勢を直すか、この警告を閉じてください。" '
            'buttons {"Dismiss"} default button "Dismiss" with icon caution giving up after 86400'
        )
        self.process = subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def is_open(self) -> bool:
        if self.process is None:
            return False
        if self.process.poll() is None:
            return True
        self.process = None
        return False

    def close(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
        self.process = None


@dataclass(frozen=True)
class ConsequenceController:
    action: ConsequenceAction
    dry_run: bool

    def run(self) -> None:
        if self.action is ConsequenceAction.NONE:
            print("Posture consequence skipped because action is none.")
            return

        errors: list[str] = []
        for command in consequence_commands(self.action):
            if self.dry_run:
                print(f"[dry-run] would run: {' '.join(command)}")
                return

            try:
                result = subprocess.run(command, capture_output=True, text=True, check=False)
            except FileNotFoundError as error:
                errors.append(str(error))
                continue
            if result.returncode == 0:
                return
            errors.append(result.stderr.strip() or result.stdout.strip())

        raise RuntimeError("; ".join(error for error in errors if error) or f"Could not run {self.action.value}.")


def consequence_command(action: ConsequenceAction) -> list[str]:
    return consequence_commands(action)[0]


def consequence_commands(action: ConsequenceAction) -> list[list[str]]:
    if action is ConsequenceAction.LOCK:
        commands = [["/usr/bin/pmset", "displaysleepnow"]]
        cg_session = "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession"
        if os.path.exists(cg_session):
            commands.append([cg_session, "-suspend"])
        commands.append(["/usr/bin/open", "-a", "ScreenSaverEngine"])
        commands.append(
            [
                "osascript",
                "-e",
                'tell application "System Events" to key code 12 using {control down, command down}',
            ]
        )
        return commands
    if action is ConsequenceAction.REBOOT:
        return [["osascript", "-e", 'tell application "System Events" to restart']]
    raise ValueError(f"No command for consequence action: {action.value}")


def consequence_action_from_trackbar(value: int) -> ConsequenceAction:
    actions = [ConsequenceAction.LOCK, ConsequenceAction.REBOOT, ConsequenceAction.NONE]
    return actions[min(max(value, 0), len(actions) - 1)]


def initial_consequence_action_value(action: ConsequenceAction) -> int:
    return [ConsequenceAction.LOCK, ConsequenceAction.REBOOT, ConsequenceAction.NONE].index(action)


def discover_wifi_device() -> str:
    result = subprocess.run(
        ["networksetup", "-listallhardwareports"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())

    lines = [line.strip() for line in result.stdout.splitlines()]
    for index, line in enumerate(lines):
        if line == "Hardware Port: Wi-Fi":
            for candidate in lines[index + 1 : index + 4]:
                if candidate.startswith("Device: "):
                    return candidate.removeprefix("Device: ").strip()
    raise RuntimeError("Could not discover Wi-Fi device. Pass --wifi-device, for example --wifi-device en0.")


def posture_features(landmarks: Iterable[object]) -> np.ndarray | None:
    import mediapipe as mp

    lm = list(landmarks)
    pose = mp.solutions.pose.PoseLandmark

    required = [
        pose.NOSE,
        pose.LEFT_SHOULDER,
        pose.RIGHT_SHOULDER,
        pose.LEFT_EAR,
        pose.RIGHT_EAR,
    ]
    if any(lm[item.value].visibility < 0.55 for item in required):
        return None

    nose = lm[pose.NOSE.value]
    left_shoulder = lm[pose.LEFT_SHOULDER.value]
    right_shoulder = lm[pose.RIGHT_SHOULDER.value]
    left_ear = lm[pose.LEFT_EAR.value]
    right_ear = lm[pose.RIGHT_EAR.value]

    shoulder_mid_x = (left_shoulder.x + right_shoulder.x) / 2.0
    shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2.0
    shoulder_width = max(abs(left_shoulder.x - right_shoulder.x), 1e-3)
    ear_mid_x = (left_ear.x + right_ear.x) / 2.0
    ear_mid_y = (left_ear.y + right_ear.y) / 2.0

    return np.array(
        [
            shoulder_mid_x * 0.35,
            shoulder_mid_y * 0.35,
            (nose.x - shoulder_mid_x) / shoulder_width,
            (nose.y - shoulder_mid_y) / shoulder_width,
            (ear_mid_x - shoulder_mid_x) / shoulder_width,
            (ear_mid_y - shoulder_mid_y) / shoulder_width,
            (left_shoulder.y - right_shoulder.y) / shoulder_width,
        ],
        dtype=np.float64,
    )


def build_profile(samples: list[np.ndarray]) -> CalibrationProfile:
    if len(samples) < 30:
        raise RuntimeError("Not enough visible-pose samples during calibration. Keep your face and shoulders in frame.")

    matrix = np.vstack(samples)
    mean = matrix.mean(axis=0)
    scale = np.maximum(matrix.std(axis=0), 0.035)
    distances = np.sqrt(np.mean(((matrix - mean) / scale) ** 2, axis=1))
    threshold = max(float(np.percentile(distances, 95) * 2.5), 2.0)
    return CalibrationProfile(mean=mean, scale=scale, threshold=threshold)


def deviation_score(features: np.ndarray, profile: CalibrationProfile) -> float:
    return float(np.sqrt(np.mean(((features - profile.mean) / profile.scale) ** 2)))


def deviation_entry_threshold(profile: CalibrationProfile, margin_ratio: float) -> float:
    return profile.threshold * (1.0 + margin_ratio)


def is_deviation_entry(score: float, profile: CalibrationProfile, margin_ratio: float) -> bool:
    return score >= deviation_entry_threshold(profile, margin_ratio)


def draw_status(frame: np.ndarray, lines: list[str], color: tuple[int, int, int]) -> None:
    import cv2

    for index, line in enumerate(lines):
        y = 32 + index * 28
        cv2.putText(frame, line, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, line, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, color, 2, cv2.LINE_AA)


def consequence_timer_line(
    now: float,
    warning_started_at: float | None,
    consequence_grace_seconds: float,
    action: ConsequenceAction,
) -> str | None:
    if warning_started_at is None:
        return None
    if action is ConsequenceAction.NONE:
        return None
    remaining = max(0.0, consequence_grace_seconds - (now - warning_started_at))
    return f"{action.value.title()} timer: {remaining:.0f}s"


def should_run_consequence(
    *,
    now: float,
    warning_started_at: float | None,
    consequence_grace_seconds: float,
    popup_enabled: bool,
    popup_open: bool,
) -> bool:
    if warning_started_at is None or now - warning_started_at < consequence_grace_seconds:
        return False
    return popup_open if popup_enabled else True


def trackbar_seconds(value: int, minimum: int = 1) -> float:
    return float(max(minimum, value))


def initial_trackbar_value(value: int, maximum: int = 60) -> int:
    return min(max(1, value), maximum)


class SettingsPanel:
    def __init__(self, initial_settings: MonitorSettings) -> None:
        configure_tk_library_paths()

        import tkinter as tk
        from tkinter import ttk

        self._tk = tk
        self._closed = False
        self.root = tk.Tk()
        self.root.title("Posture Guard Settings")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        frame = ttk.Frame(self.root, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")

        self.calibration_seconds = tk.IntVar(value=int(initial_settings.calibration_seconds))
        self.deviation_seconds = tk.IntVar(value=int(initial_settings.deviation_seconds))
        self.wifi_off_enabled = tk.BooleanVar(value=initial_settings.wifi_off_enabled)
        self.consequence_grace_seconds = tk.IntVar(value=int(initial_settings.consequence_grace_seconds))
        self.consequence_action = tk.StringVar(value=initial_settings.consequence_action.value)
        self.popup_enabled = tk.BooleanVar(value=initial_settings.popup_enabled)

        self._add_scale(frame, 0, "Calibration sec", self.calibration_seconds, 1, 60)
        self._add_scale(frame, 1, "Deviation sec", self.deviation_seconds, 1, 60)
        self._add_scale(frame, 2, "Grace sec", self.consequence_grace_seconds, 1, 300)

        ttk.Checkbutton(frame, text="Turn Wi-Fi off after deviation", variable=self.wifi_off_enabled).grid(
            row=3,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(10, 0),
        )

        action_frame = ttk.LabelFrame(frame, text="Action", padding=8)
        action_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        for column, action in enumerate(ConsequenceAction):
            ttk.Radiobutton(
                action_frame,
                text=action.value.title(),
                value=action.value,
                variable=self.consequence_action,
            ).grid(row=0, column=column, padx=(0, 12), sticky="w")

        ttk.Checkbutton(frame, text="Show warning popup", variable=self.popup_enabled).grid(
            row=5,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(10, 0),
        )

    def _add_scale(self, parent: object, row: int, label: str, variable: object, from_: int, to: int) -> None:
        from tkinter import ttk

        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Scale(parent, from_=from_, to=to, variable=variable, orient="horizontal", length=220).grid(
            row=row,
            column=1,
            sticky="ew",
            padx=8,
            pady=4,
        )
        ttk.Label(parent, textvariable=variable, width=4, anchor="e").grid(row=row, column=2, sticky="e", pady=4)

    def poll(self) -> MonitorSettings | None:
        if self._closed:
            return None
        try:
            self.root.update_idletasks()
            self.root.update()
        except self._tk.TclError:
            self._closed = True
            return None
        return MonitorSettings(
            calibration_seconds=trackbar_seconds(self.calibration_seconds.get()),
            deviation_seconds=trackbar_seconds(self.deviation_seconds.get()),
            wifi_off_enabled=self.wifi_off_enabled.get(),
            consequence_action=ConsequenceAction(self.consequence_action.get()),
            consequence_grace_seconds=trackbar_seconds(self.consequence_grace_seconds.get()),
            popup_enabled=self.popup_enabled.get(),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.root.destroy()
        except self._tk.TclError:
            pass


def configure_tk_library_paths() -> None:
    python_root = sys.base_prefix
    tcl_library = os.path.join(python_root, "lib", "tcl9.0")
    tk_library = os.path.join(python_root, "lib", "tk9.0")
    if "TCL_LIBRARY" not in os.environ and os.path.exists(os.path.join(tcl_library, "init.tcl")):
        os.environ["TCL_LIBRARY"] = tcl_library
    if "TK_LIBRARY" not in os.environ and os.path.exists(os.path.join(tk_library, "tk.tcl")):
        os.environ["TK_LIBRARY"] = tk_library


def settings_lines(
    action: ConsequenceAction,
    grace_seconds: float,
    popup_enabled: bool,
    wifi_off_enabled: bool,
) -> list[str]:
    popup = "on" if popup_enabled else "off"
    wifi_off = "on" if wifi_off_enabled else "off"
    return [f"Wi-Fi off: {wifi_off}  Action: {action.value}  Grace: {grace_seconds:.0f}s  Popup: {popup}"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate posture and turn off Mac Wi-Fi after sustained deviation.")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument("--wifi-device", default="auto", help="Wi-Fi device, or auto. Usually en0 on Mac.")
    parser.add_argument("--dry-run", action="store_true", help="Do not turn Wi-Fi off; print the command instead.")
    parser.add_argument("--calibration-seconds", type=int, default=10)
    parser.add_argument("--deviation-seconds", type=int, default=5)
    parser.add_argument(
        "--consequence-action",
        choices=[action.value for action in ConsequenceAction],
        default=ConsequenceAction.LOCK.value,
        help="Action after sustained posture deviation beyond the grace period.",
    )
    parser.add_argument(
        "--consequence-grace-seconds",
        "--reboot-grace-seconds",
        type=float,
        default=30.0,
        help="Run the consequence action if posture has not improved for this many seconds.",
    )
    parser.add_argument("--warning-popup", dest="warning_popup", action="store_true", default=True)
    parser.add_argument("--no-warning-popup", dest="warning_popup", action="store_false")
    parser.add_argument(
        "--deviation-margin",
        type=float,
        default=0.15,
        help="Extra score margin required before deviation starts. 0.15 means 15%% above the calibrated threshold.",
    )
    parser.add_argument("--recovery-poll-seconds", type=float, default=2.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    wifi = WifiController.create(args.wifi_device, args.dry_run)
    initial_consequence_action = ConsequenceAction(args.consequence_action)
    warning_popup = PostureWarningPopup()
    settings_panel = SettingsPanel(
        MonitorSettings(
            calibration_seconds=trackbar_seconds(args.calibration_seconds),
            deviation_seconds=trackbar_seconds(args.deviation_seconds),
            wifi_off_enabled=True,
            consequence_action=initial_consequence_action,
            consequence_grace_seconds=trackbar_seconds(int(args.consequence_grace_seconds)),
            popup_enabled=args.warning_popup,
        )
    )
    print(f"Wi-Fi device: {wifi.device}")

    import cv2
    import mediapipe as mp

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        settings_panel.close()
        print(f"Could not open camera index {args.camera}.", file=sys.stderr)
        return 1

    mp_pose = mp.solutions.pose
    mp_draw = mp.solutions.drawing_utils
    window_name = "Posture Guard"
    cv2.namedWindow(window_name)

    state = MonitorState.READY
    state_started_at = time.monotonic()
    deviation_started_at: float | None = None
    warning_started_at: float | None = None
    last_recovery_poll_at = 0.0
    calibration_samples: list[np.ndarray] = []
    active_calibration_seconds = trackbar_seconds(args.calibration_seconds)
    profile: CalibrationProfile | None = None

    try:
        with mp_pose.Pose(model_complexity=1, min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
            while True:
                settings = settings_panel.poll()
                if settings is None:
                    return 0

                ok, frame = cap.read()
                if not ok:
                    print("Could not read from camera.", file=sys.stderr)
                    return 1

                now = time.monotonic()
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = pose.process(rgb)
                features = None
                if result.pose_landmarks:
                    mp_draw.draw_landmarks(frame, result.pose_landmarks, mp_pose.POSE_CONNECTIONS)
                    features = posture_features(result.pose_landmarks.landmark)

                calibration_seconds = settings.calibration_seconds
                deviation_seconds = settings.deviation_seconds
                wifi_off_enabled = settings.wifi_off_enabled
                consequence_action = settings.consequence_action
                consequence_grace_seconds = settings.consequence_grace_seconds
                popup_enabled = settings.popup_enabled
                consequence = ConsequenceController(action=consequence_action, dry_run=args.dry_run)
                if not popup_enabled:
                    warning_popup.close()

                if state is MonitorState.READY:
                    lines = [
                        "Ready: sit in reference posture",
                        "Press c to calibrate, q to quit",
                        f"Calibration: {calibration_seconds:.0f}s  Deviation: {deviation_seconds:.0f}s",
                        *settings_lines(consequence_action, consequence_grace_seconds, popup_enabled, wifi_off_enabled),
                    ]
                    if args.dry_run:
                        lines.insert(0, "DRY RUN: Wi-Fi will not turn off")
                    draw_status(
                        frame,
                        lines,
                        (255, 255, 255),
                    )

                elif state is MonitorState.CALIBRATING:
                    if features is not None:
                        calibration_samples.append(features)
                    remaining = max(0.0, active_calibration_seconds - (now - state_started_at))
                    draw_status(
                        frame,
                        [f"Calibrating reference posture: {remaining:0.1f}s", f"samples: {len(calibration_samples)}"],
                        (0, 255, 255),
                    )
                    if remaining <= 0:
                        try:
                            profile = build_profile(calibration_samples)
                        except RuntimeError as error:
                            print(f"Calibration failed: {error}")
                            print("Press c to try calibration again.")
                            state = MonitorState.MONITORING if profile is not None else MonitorState.READY
                            state_started_at = now
                            calibration_samples = []
                        else:
                            state = MonitorState.MONITORING
                            state_started_at = now
                            print(f"Calibration complete. Deviation threshold: {profile.threshold:.2f}")

                elif state is MonitorState.MONITORING:
                    if features is None or profile is None:
                        deviation_started_at = None
                        draw_status(frame, ["Monitoring: pose not visible", "Keep face and shoulders in frame"], (0, 165, 255))
                    else:
                        score = deviation_score(features, profile)
                        entry_threshold = deviation_entry_threshold(profile, args.deviation_margin)
                        is_deviating = is_deviation_entry(score, profile, args.deviation_margin)
                        if is_deviating and deviation_started_at is None:
                            deviation_started_at = now
                            warning_started_at = now
                            if popup_enabled:
                                warning_popup.show_count_started()
                        elif not is_deviating:
                            deviation_started_at = None
                            warning_started_at = None
                            warning_popup.close()

                        elapsed = 0.0 if deviation_started_at is None else now - deviation_started_at
                        lines = [
                            f"Monitoring: score {score:.2f} / {profile.threshold:.2f}",
                            f"Off starts at: {entry_threshold:.2f}",
                            f"Deviation: {elapsed:.1f}s / {deviation_seconds:.1f}s",
                            *settings_lines(consequence_action, consequence_grace_seconds, popup_enabled, wifi_off_enabled),
                            "Press c to recalibrate, q to quit",
                        ]
                        popup_open = warning_popup.is_open()
                        timer_line = consequence_timer_line(
                            now,
                            warning_started_at,
                            consequence_grace_seconds,
                            consequence.action,
                        )
                        if is_deviating and (popup_open or not popup_enabled) and timer_line is not None:
                            lines.insert(4, timer_line)
                        draw_status(
                            frame,
                            lines,
                            (0, 0, 255) if is_deviating else (0, 255, 0),
                        )
                        if (
                            is_deviating
                            and consequence.action is not ConsequenceAction.NONE
                            and warning_started_at is not None
                            and should_run_consequence(
                                now=now,
                                warning_started_at=warning_started_at,
                                consequence_grace_seconds=consequence_grace_seconds,
                                popup_enabled=popup_enabled,
                                popup_open=popup_open,
                            )
                        ):
                            print(f"Posture did not improve. Running consequence action: {consequence.action.value}.")
                            consequence.run()
                            return 0
                        if elapsed >= deviation_seconds and wifi_off_enabled:
                            print("Posture deviation sustained. Turning Wi-Fi off.")
                            wifi.turn_off()
                            if not args.dry_run:
                                print("Wi-Fi off confirmed.")
                            state = MonitorState.WAITING_MANUAL_RECOVERY
                            state_started_at = now
                            deviation_started_at = None
                            last_recovery_poll_at = 0.0

                elif state is MonitorState.WAITING_MANUAL_RECOVERY:
                    lines = [
                        "Wi-Fi is off",
                        "Turn Wi-Fi on manually to resume monitoring",
                        *settings_lines(consequence_action, consequence_grace_seconds, popup_enabled, wifi_off_enabled),
                        "Press q to quit",
                    ]
                    popup_open = warning_popup.is_open()
                    timer_line = consequence_timer_line(
                        now,
                        warning_started_at,
                        consequence_grace_seconds,
                        consequence.action,
                    )
                    if timer_line is not None and (popup_open or not popup_enabled):
                        lines.insert(2, timer_line)
                    draw_status(frame, lines, (0, 165, 255))
                    if warning_started_at is not None and profile is not None:
                        posture_improved = False
                        if features is not None:
                            score = deviation_score(features, profile)
                            posture_improved = not is_deviation_entry(score, profile, args.deviation_margin)
                        if posture_improved:
                            warning_started_at = None
                            warning_popup.close()
                        elif consequence.action is not ConsequenceAction.NONE and should_run_consequence(
                            now=now,
                            warning_started_at=warning_started_at,
                            consequence_grace_seconds=consequence_grace_seconds,
                            popup_enabled=popup_enabled,
                            popup_open=popup_open,
                        ):
                            print(f"Posture did not improve. Running consequence action: {consequence.action.value}.")
                            consequence.run()
                            return 0
                    if args.dry_run:
                        state = MonitorState.MONITORING
                        state_started_at = now
                    elif now - last_recovery_poll_at >= args.recovery_poll_seconds:
                        last_recovery_poll_at = now
                        if wifi.is_on():
                            print("Manual recovery detected. Monitoring resumed.")
                            state = MonitorState.MONITORING
                            state_started_at = now

                cv2.imshow(window_name, frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    return 0
                if key == ord("c") and state in {MonitorState.READY, MonitorState.MONITORING}:
                    calibration_samples = []
                    active_calibration_seconds = calibration_seconds
                    state = MonitorState.CALIBRATING
                    state_started_at = now
                    deviation_started_at = None
                    warning_started_at = None
                    warning_popup.close()
                    print(f"Calibration started for {active_calibration_seconds:.0f}s.")
    except KeyboardInterrupt:
        print("Interrupted. Exiting.")
        return 130
    finally:
        warning_popup.close()
        settings_panel.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
