# RPiT3K General

Current rpi-ui DSP and web interface, adapted for Linux ALSA interfaces on ARM64 and x86-64. Experimental: not yet compiled or tested on x86-64 or physical USB audio by the maintainer. Raspberry Pi OS / Debian / Ubuntu with systemd and 64-bit userspace are installer targets. 32-bit systems are not supported. Other Linux distributions require equivalent dependencies and manual CMake build.

## Install

Stop any existing RPiT3K service before installing. Use a separate checkout, as both branches build to build-rpi.

```bash
sudo apt update
sudo apt install -y git
git clone --branch rpi-general https://github.com/tinker-net/RPiT3K.git RPiT3K-General
cd RPiT3K-General
aplay -l
arecord -l
bash rpi/install-general.sh
```

This installs compiler, ALSA and Python dependencies, pins NAM Core, builds, executes offline regression tests and installs rpit3k-general.service. Local data lives in ~/.local/share/rpit3k-general, separate from Pisound edition. Existing settings are preserved when reinstalling. The default PCM is default, with 256 frames and three periods, capture channel 1 and two playback outputs. Audio readiness is checked using live meters; a controller may be installed successfully while hardware configuration is still required.

## Configure interface

Use an SSH tunnel from another machine:
```bash
ssh -N -L 8080:127.0.0.1:8080 USER@HOST
```
Open http://localhost:8080. Expand Audio settings & diagnostics, scan devices, choose the same duplex ALSA PCM for capture/playback, configure channels and press Apply audio settings. If audio is stopped, press Start to test a preset. A failed restart attempts to restore prior settings.

Example for a two-channel Scarlett with guitar on input 2 (replace CARD with actual ALSA card ID from aplay/arecord):
```bash
bash rpi/install-general.sh --device plughw:CARD=USB,DEV=0 --input-channel 2 --buffer 256
```

The example ID USB is a placeholder, not a detected Scarlett ID. On multichannel interfaces set --input-channels and --output-channels to supported counts, then choose --input-channel, --output-left, --output-right (one-based). For mono output choose both output channels as 1 and output count 1. Unselected outputs receive silence. A single shared PCM is used; separate unsynchronized audio interfaces are not supported. Direct hardware monitoring should be disabled to avoid mixing processed and dry signals. Lower output volume before starting.

hw: uses direct hardware access; plughw: allows ALSA format/channel/rate conversion if needed. The application requests 48 kHz S32_LE and exact buffer/period geometry; incompatible configurations may be rejected. Try 128, 256 or 512 frames, 2–4 periods or an appropriate ALSA PCM. Not every driver/interface exposes compatible full-duplex streaming. No automatic hotplug recovery is promised.

## Calibration

Set ADC full-scale reference in dBu for the actual interface and analog gain position, then use Calibrate Input to read NAM input_level_dbu metadata. No generic reference is assumed. Changing input routing invalidates an unchanged stored reference. Recalibrate after changing analog gain. No automatic physical voltage measurement is performed.

## Access and service

Default is localhost, no authentication, cloud disabled. For trusted isolated LAN only, add --lan at installation; never expose port 8080 to the Internet. --cloud is experimental and not validated. No Pisound driver, button or hotspot is automatically installed. For a dedicated Pisound installation use rpi-ui.

```bash
sudo systemctl status rpit3k-general
sudo journalctl -u rpit3k-general -n 100 --no-pager
```

Updates: stop service, git pull --ff-only origin rpi-general, rebuild, run ctest and --bypass --verify, then start service. To uninstall, disable and remove rpit3k-general.service and reload systemd; preserve or back up local data.

## Validation

The existing Pi 5 DSP results are documented in the main README and are inherited, not new measurements for this branch. Compile and run regression tests on each architecture, verify selected capture and output routing, measure live xruns and timing, and test analog latency and calibration. Performance and compatibility with arbitrary interfaces cannot be guaranteed by class compliance alone.

## Optional host shutdown button

After installing the service, run `bash rpi/install-poweroff.sh` as its normal user and confirm. The top-left power button asks for confirmation before stopping audio and requesting a systemd poweroff. The helper installs a root-owned sudoers rule limited to the exact poweroff command and a service environment flag. On unauthenticated LAN mode, anyone with API access can shut down the host: enable only on a trusted isolated network. Disable with `bash rpi/install-poweroff.sh --disable` before uninstalling the service. The button does not physically disconnect power or switch the device back on.
