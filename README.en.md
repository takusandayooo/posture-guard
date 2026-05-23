<div id="top"></div>

# Posture Guard

<p>
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB.svg?logo=python&style=for-the-badge&logoColor=white" alt="Python 3.11 or 3.12">
  <img src="https://img.shields.io/badge/uv-managed-2C5F2D.svg?style=for-the-badge" alt="uv managed">
  <img src="https://img.shields.io/badge/OpenCV-camera-5C3EE8.svg?logo=opencv&style=for-the-badge&logoColor=white" alt="OpenCV">
  <img src="https://img.shields.io/badge/MediaPipe-pose-0097A7.svg?style=for-the-badge" alt="MediaPipe">
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows-supported-000000.svg?style=for-the-badge" alt="macOS and Windows">
</p>

Posture Guard is a desktop app that watches your posture through a webcam. It compares your current posture with your own calibrated reference posture, then interrupts work with Wi-Fi shutdown, screen lock, reboot, or no extra action when the deviation lasts too long.

日本語版は [README.md](README.md) を参照してください。

## Table of Contents

1. [About](#about)
2. [Tech Stack](#tech-stack)
3. [Requirements](#requirements)
4. [Directory Structure](#directory-structure)
5. [Setup](#setup)
6. [Usage](#usage)
7. [Commands and Options](#commands-and-options)
8. [OS Notes](#os-notes)
9. [Posture Scoring](#posture-scoring)
10. [Troubleshooting](#troubleshooting)
11. [Development](#development)

## About

Long desk sessions make it easy to drift into a rounded back and forward head position without noticing. Posture Guard makes that drift painful for your workflow: if posture deviation continues past the configured timers, it can turn off Wi-Fi and optionally lock or reboot the machine.

The app does not judge a universal correct posture. You first capture your own Reference Posture, and every later observation is compared against that baseline.

Features:

- Calibrates a personal Reference Posture through a webcam
- Detects sustained Posture Deviation from that baseline
- Shows warnings before running disruptive actions
- Supports Wi-Fi shutdown, screen lock, reboot, or no extra consequence
- Requires Manual Recovery for Wi-Fi instead of reconnecting automatically
- Supports macOS and Windows
- Provides `--dry-run` for checking behavior without changing OS state

<p align="right">(<a href="#top">Back to top</a>)</p>

## Tech Stack

| Category | Technology | Purpose |
| --- | --- | --- |
| Language | Python | CLI and posture monitoring |
| Package manager | uv | Dependency sync, execution, tests |
| Pose estimation | MediaPipe | Face, ear, and shoulder landmark detection |
| Camera/rendering | OpenCV | Camera input, preview window, status rendering |
| Numeric processing | NumPy | Posture features, thresholds, scores |
| Settings UI | Tkinter | Runtime settings panel |
| Tests | pytest | Unit tests and optional Wi-Fi integration test |

<p align="right">(<a href="#top">Back to top</a>)</p>

## Requirements

| Item | Version/Condition |
| --- | --- |
| Python | 3.11 or 3.12 |
| OS | macOS or Windows |
| Camera | A webcam accessible from OpenCV |
| macOS Wi-Fi control | `networksetup` must be available |
| Windows Wi-Fi control | PowerShell `Get-NetAdapter`, `Disable-NetAdapter`, and `Enable-NetAdapter` must be available |

Use Python 3.11 or 3.12 because MediaPipe may not publish wheels for newer Python versions.

No environment variables are required for normal use. The real Wi-Fi integration test runs only when `POSTURE_GUARD_RUN_WIFI_INTEGRATION=1` is set.

<p align="right">(<a href="#top">Back to top</a>)</p>

## Directory Structure

```text
.
├── README.md
├── README.en.md
├── CONTEXT.md
├── pyproject.toml
├── uv.lock
├── src
│   └── posture_guard
│       ├── __init__.py
│       └── cli.py
└── tests
    ├── test_cli.py
    └── test_wifi_integration.py
```

| Path | Purpose |
| --- | --- |
| `src/posture_guard/cli.py` | CLI, posture monitoring, Wi-Fi control, warning, and consequence actions |
| `tests/test_cli.py` | Unit tests for scoring, command generation, and settings behavior |
| `tests/test_wifi_integration.py` | Optional integration test that toggles real Wi-Fi power |
| `CONTEXT.md` | Domain language and design assumptions |
| `pyproject.toml` | Project metadata, dependencies, and CLI entry point |

<p align="right">(<a href="#top">Back to top</a>)</p>

## Setup

1. Install Python 3.11 or 3.12.
2. Install `uv`.
3. Sync dependencies.

```sh
uv sync
```

Start with dry run mode. It prints the OS commands that would run, but does not turn off Wi-Fi, lock the screen, or reboot.

```sh
uv run posture-guard --dry-run
```

<p align="right">(<a href="#top">Back to top</a>)</p>

## Usage

1. Start the app.
2. The camera preview and settings panel open.
3. Sit in your preferred good posture and press `c` to calibrate.
4. The app monitors posture through the webcam.
5. When posture deviation is detected, a warning and countdown appear.
6. If the deviation lasts longer than the configured timer, Wi-Fi is turned off.
7. If the posture still does not recover, the configured consequence action runs.
8. Turn Wi-Fi back on manually.

Run with real Wi-Fi control enabled:

```sh
uv run posture-guard
```

Keyboard shortcuts:

| Key | Action |
| --- | --- |
| `c` | Calibrate or recalibrate the reference posture |
| `q` | Quit |

Runtime settings:

| Setting | Meaning |
| --- | --- |
| Calibration sec | Seconds used to capture the reference posture |
| Deviation sec | Seconds of deviation before Wi-Fi shutdown |
| Grace sec | Seconds before the extra consequence action |
| Turn Wi-Fi off after deviation | Whether posture deviation turns Wi-Fi off |
| Action | `lock`, `reboot`, or `none` |
| Show warning popup | Whether to show a warning popup |

<p align="right">(<a href="#top">Back to top</a>)</p>

## Commands and Options

### Commands

| Command | Description |
| --- | --- |
| `uv sync` | Install dependencies and sync the virtual environment |
| `uv run posture-guard --dry-run` | Start without changing OS state |
| `uv run posture-guard` | Start with Wi-Fi control enabled |
| `uv run posture-guard --camera 1` | Start with a specific camera index |
| `uv run posture-guard --wifi-device en0` | Start with a specific Wi-Fi device |
| `uv run pytest` | Run tests |

### CLI Options

| Option | Default | Description |
| --- | --- | --- |
| `--camera` | `0` | OpenCV camera index |
| `--wifi-device` | `auto` | Wi-Fi device or adapter name |
| `--dry-run` | `false` | Print commands without changing OS state |
| `--calibration-seconds` | `10` | Seconds used for calibration |
| `--deviation-seconds` | `5` | Seconds of sustained deviation before Wi-Fi shutdown |
| `--consequence-action` | `lock` | Extra action after grace period: `lock`, `reboot`, or `none` |
| `--consequence-grace-seconds` | `30` | Seconds before the extra action |
| `--warning-popup` | `true` | Show warning popup |
| `--no-warning-popup` | `false` | Disable warning popup |
| `--deviation-margin` | `0.15` | Extra score margin before countdown starts |
| `--recovery-poll-seconds` | `2.0` | Poll interval for manual Wi-Fi recovery |

<p align="right">(<a href="#top">Back to top</a>)</p>

## OS Notes

### Windows

Windows uses PowerShell `Get-NetAdapter`, `Disable-NetAdapter`, and `Enable-NetAdapter` to control the Wi-Fi adapter. Run the terminal as Administrator when using real Wi-Fi shutdown.

If auto detection fails, pass the adapter name.

```sh
uv run posture-guard --wifi-device "Wi-Fi"
```

### macOS

macOS uses `networksetup` for Wi-Fi control. If auto detection fails, pass the device name.

```sh
uv run posture-guard --wifi-device en0
```

For screen lock, the app tries display sleep, user session suspension, screen saver launch, and a keyboard shortcut. Make sure macOS requires a password after sleep or screen saver starts.

<p align="right">(<a href="#top">Back to top</a>)</p>

## Posture Scoring

The on-screen `score / threshold` value shows how far the current posture is from the calibrated reference posture. The score uses shoulder position, head position relative to the shoulders, and shoulder tilt.

To avoid overreacting to small camera shifts, shoulder position is weighted less than head position. A tiny threshold crossing such as `3.01 / 3.00` does not start the Wi-Fi countdown. By default, countdown starts when the score is 15% above the threshold. The camera window shows this value as `Off starts at`.

<p align="right">(<a href="#top">Back to top</a>)</p>

## Troubleshooting

### `uv` fails with cache permissions

Use a writable cache directory.

```sh
UV_CACHE_DIR=.uv-cache uv sync
UV_CACHE_DIR=.uv-cache uv run posture-guard --dry-run
```

### Calibration fails

Make sure your face, ears, and both shoulders are visible. Increase the calibration seconds if needed. Very short calibration windows may not collect enough samples.

### The camera does not open

Check OS camera permissions and try another camera index.

```sh
uv run posture-guard --camera 1
```

### Wi-Fi device auto detection fails

Pass the device or adapter name explicitly.

```sh
uv run posture-guard --wifi-device en0
uv run posture-guard --wifi-device "Wi-Fi"
```

### Windows cannot turn Wi-Fi off

Run the terminal as Administrator. PowerShell network adapter changes require elevated permissions.

### macOS does not lock the screen

Check that macOS requires a password after sleep or screen saver starts. Some environments may only trigger display sleep.

<p align="right">(<a href="#top">Back to top</a>)</p>

## Development

Run regular tests:

```sh
uv run pytest
```

Run the integration test that toggles real Wi-Fi:

```sh
POSTURE_GUARD_RUN_WIFI_INTEGRATION=1 uv run pytest tests/test_wifi_integration.py
```

Run the integration test only when you intentionally want the machine's Wi-Fi connection to be interrupted.

<p align="right">(<a href="#top">Back to top</a>)</p>
