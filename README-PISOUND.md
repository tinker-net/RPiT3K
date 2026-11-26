# RPi-Ton3K — Blokas Pisound user guide

See [overview](README.md), [technical guide](rpi/README.md) and [validation](docs/DAISYSP_VALIDATION.md). 64-bit Raspberry Pi OS Lite with compatible Pisound; Pi 5 developer-tested, Pi 4/CM4/400 candidate, older Pi experimental. 32-bit and Pisound Micro not supported by this installer.

## Install

Normal sudo-enabled user, not root. Reliable power/cooling, preferably 2 GB or more RAM for compiling. Stop competing audio programs and lower monitor volume. Power off before attaching Pisound. Follow Blokas driver installation if necessary.

```sh
sudo apt update
sudo apt install -y git
git clone --branch rpi-ui https://github.com/tinker-net/RPiT3K.git
cd RPiT3K
# If Blokas driver is not installed:\nbash rpi/install-pisound.sh --install-blokas\n# Reboot, reconnect, then:\n# cd ~/RPiT3K\nbash rpi/install-pisound.sh
```

The optional Blokas step downloads the vendor's current unpinned installer and exits; reboot before running normal installation. Confirm aplay -l and arecord -l show Pisound. Pi 5 initial 64×3, Pi 4 128×3, older Pi 256×3. Fixed left capture/dual mono playback.

Installer installs dependencies, pins NAM Core, compiles, runs CTest and offline verification, installs/enables rpit3k.service. Existing settings/data preserved; initial buffer/routing flags do not overwrite existing settings. New readiness check verifies controller available **with audio stopped**, not ALSA streaming. Fresh installer not yet independently tested. --jobs 1 reduces build memory use. For updates stop service first.

## Access

Default loopback HTTP; SSH tunnel from another computer:
```sh
ssh -N -L 8080:127.0.0.1:80 USER@HOST
```
Open http://localhost:8080 through the SSH tunnel, or http://HOST directly in LAN mode (port 80). Existing source installations can migrate without changing their configuration using `bash rpi/migrate-http-port.sh`. Explicit --lan at install exposes unauthenticated HTTP to the trusted isolated LAN, including library and cloud/power access. Never expose to Internet/untrusted network. For existing build use bash rpi/install-service.sh --lan; repeat --button/--cloud if desired.

## First use

Audio starts OFF every time. Last preset is selected, not playing. Import your own .nam and mono WAV IRs (up to 1 s after resampling to 48 kHz); use either NAM slot or both serially, optionally two parallel IRs. Choose Full/Lite only meaningfully for slimmable models. Disable NAM/IR bypass, start Audio with low output. Gate at -81 is off. Six knobs control input, gate, bass, mid, treble, output. Preset changes while running swap rigs with a brief fade, not guaranteed gapless; audio hardware setting changes reopen streams. While stopped edits autosave without opening ALSA.

Effects toolbar opens individual dialogs; Enable illuminates icon yellow and unlocks controls. Turning off remembers values. Compressor PRE/POST, chorus mix/rate/depth, delay mix/time/feedback, reverb mix/decay (.3–5 s)/Dark-Bright-Neutral. Hi-Z has independent enable and four pickup profiles; use only for assumed low impedance passive pickup loading, not external buffer or high-Z input. Tuner mutes output; practice metronome requires audio on. Calibration uses first active capture metadata and ADC reference, applies explicit input gain; nominal +1.14 dBu reference is an estimate at minimum analog gain, not measured for your hardware. Do not assume missing metadata means invalid capture.

Library search, folders, favorites, import/move/rename, confirmed permanent deletion. Sidebars can be hidden/resized; custom amp artwork is visual only. Four slots save automatically. Browser layout stored locally.

## Optional cloud and power

--cloud enables experimental TONE3000 device OAuth; use personal publishable key, never secret key. Session persists in private tone3000-session.json; disconnect deletes it. Mock tests pass, actual reboot/login/download not yet independently verified. API terms apply; no official affiliation. Local audio never requires cloud. Original USB Companion cannot control this Linux rig.

Optional power menu: run bash rpi/install-poweroff.sh as service user and confirm; exact systemctl poweroff and reboot sudo privileges only, no general root access. Existing poweroff-only installs must rerun helper for reboot. Disable with bash rpi/install-poweroff.sh --disable. On LAN anyone with API access can invoke confirmed power actions. No physical power switching.

Optional autonomous Pisound controls: `bash rpi/install-button.sh` (or `--button` on service installation). Single click toggles NAM 1, double cycles presets with a single confirmation flash, triple toggles hotspot, HOLD_1S identifies the current preset with 1–4 LED flashes, HOLD_3S toggles audio with one long/short confirmation flash, HOLD_5S invokes Blokas shutdown. Audio starts OFF; stomp is saved per preset, only NAM 1 is bypassed with a 10 ms ramp. Hotspot uses existing RPiT3K-fallback if installed, otherwise Blokas script; manual off suppresses fallback until reboot or manual on. Existing config backed up. Hardware verification pending. The versioned [button mapping](rpi/pisound-button.conf) is the canonical six-gesture configuration; the installer changes only those mappings and preserves the other Blokas settings.

### Debian edition

The separate `rpi-ton3k-pisound` ARM64 package is built from this source edition, not the generic ALSA edition. It uses fixed Pisound routing, 48 kHz, 64 × 3 on Pi 5, audio OFF at startup, and installs the six button gestures, fallback hotspot and power controls. The package requires the official Blokas APT repository and its `pisound` dependency; the kernel/overlay must support the board and may require a reboot. LAN access and cloud integration are enabled in the dedicated package profile; use only a trusted network. A new hotspot gets a unique local password; no maintainer credentials, models or presets are shipped. See [Debian packaging guide](https://github.com/tinker-net/RPiT3K/blob/deb-packaging/packaging/README.md) for installation and migration. The packaged deployment is not yet validated on physical hardware.

## Update and troubleshoot

```sh
cd ~/RPiT3K
sudo systemctl stop rpit3k
git pull --ff-only origin rpi-ui
cmake --build build-rpi -j2
ctest --test-dir build-rpi --output-on-failure
./build-rpi/rpit3k --bypass --verify
sudo systemctl start rpit3k
```

Run sequentially and stop on failures. Service restarts with audio OFF. If audio fails check browser logs, aplay -l, arecord -l, sudo journalctl -u rpit3k -n 100 --no-pager. Increase period size/count if xruns; counter includes suspend recoveries, nominal per-direction buffer not round-trip latency. Audio OFF means no valid live meters; controller can be healthy without audio. 

Data lives in ~/.local/share/rpit3k. Back up privately, including library/settings/presets/favorites/artwork; OAuth file contains secrets, never share. Uninstall by disabling power helper (if enabled), disabling/stopping service, removing service unit and reloading systemd; preserve data unless deliberately deleting it. Restore Pisound button backup if appropriate, remove optional hotspot separately. No commercial models provided. See technical guide for licenses and current test limitations.
