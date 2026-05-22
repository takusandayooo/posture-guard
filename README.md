# Posture Guard

Posture Guard calibrates your good sitting posture from the webcam, then turns off Mac Wi-Fi when your posture deviates for long enough.

## Setup

```sh
uv sync
```

This project requires Python 3.11 or 3.12 because MediaPipe may not provide wheels for newer Python versions.

## Run

Dry run first:

```sh
uv run posture-guard --dry-run
```

Real Wi-Fi control:

```sh
uv run posture-guard
```

Flow:

1. Adjust the settings in the Tkinter settings window.
2. Sit in your good posture.
3. Press `c` to start calibration.
4. The app records your reference posture for the selected calibration time.
5. Monitoring starts.
6. When posture deviation starts counting, a warning popup appears if `Popup` is on.
7. If posture deviation continues for the selected deviation time, Wi-Fi is turned off if that setting is enabled.
8. If posture does not improve before the grace timer ends, the selected action runs. The default action locks the screen.
9. Monitoring waits while Wi-Fi is off.
10. When you manually turn Wi-Fi back on, monitoring resumes.

Settings window controls:

- `Calibration sec`: reference posture calibration time.
- `Deviation sec`: Wi-Fi-off delay after posture deviation starts.
- `Turn Wi-Fi off after deviation`: turn Wi-Fi off or leave it on when the deviation timer ends.
- `Action`: action after the grace timer ends (`Lock`, `Reboot`, or `None`).
- `Grace sec`: grace timer before the action runs.
- `Show warning popup`: show or hide the warning popup.

Keys:

- `c`: start calibration or recalibrate
- `q`: quit

The `score / threshold` display shows how far the current posture is from the calibrated reference posture. The score uses shoulder position, head position relative to the shoulders, and shoulder tilt. Shoulder position has a lighter weight than head position so small camera framing shifts do not dominate the score. Wi-Fi shutdown does not start at a tiny crossing like `3.01 / 3.00`; by default it starts when the score is 15% above the threshold. The window shows that value as `Off starts at`.

The camera window shows the current action, grace timer, and popup setting. Lock uses display sleep first, so make sure macOS is set to require a password after sleep or screen saver. Reboot uses macOS System Events, so it does not ask for a sudo password. `--dry-run` prints commands instead of running them.

If calibration fails, increase `Calibration sec` and keep your face and shoulders in frame. Very short calibration times such as 1 second may not collect enough visible-pose samples.
