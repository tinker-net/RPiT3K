# RPi-Ton3K — General ALSA user guide

See [overview](README.md), [technical guide](rpi/README.md) and [validation](docs/DAISYSP_VALIDATION.md). 64-bit Debian/Ubuntu/Raspberry Pi OS on aarch64 or x86_64; hardware compatibility is experimental.

## Install

Normal sudo-enabled user, not root. Reliable power/cooling, preferably 2 GB or more RAM for compiling. Stop competing audio programs and lower monitor volume. Check aplay -l and arecord -l for your interface; driver must already work.

```sh
sudo apt update
sudo apt install -y git
git clone --branch rpi-general https://github.com/tinker-net/RPiT3K.git
cd RPiT3K
bash rpi/install-general.sh
```

Initial PCM default, 256×3, capture channel 1 of 2, output channels 1/2 of 2. Example: `bash rpi/install-general.sh --device plughw:CARD=USB,DEV=0 --input-channel 2 --buffer 256` (USB is a placeholder). Flags --input-channels, --output-channels, --output-left, --output-right support 1–64; choose both outputs 1 for mono. Configure supported channel counts and PCM in Audio settings; a single duplex PCM is used. Disable hardware direct monitoring if unwanted.

Installer installs dependencies, pins NAM Core, compiles, runs CTest and offline verification, installs/enables rpit3k-general.service. Existing settings/data preserved; initial buffer/routing flags do not overwrite existing settings. New readiness check verifies controller available **with audio stopped**, not ALSA streaming. Fresh installer not yet independently tested. --jobs 1 reduces build memory use. For updates stop service first.

## Access

Default loopback HTTP; SSH tunnel from another computer:
```sh
ssh -N -L 8080:127.0.0.1:8080 USER@HOST
```
Open http://localhost:8080. Explicit --lan at install exposes unauthenticated HTTP to the trusted isolated LAN, including library and cloud/power access. Never expose to Internet/untrusted network. Repeat install-general.sh with desired flags to change bind/cloud; existing routing settings are preserved.

## First use

Audio starts OFF every time. Last preset is selected, not playing. Import your own .nam and mono WAV IRs (up to 1 s after resampling to 48 kHz); use either NAM slot or both serially, optionally two parallel IRs. Choose Full/Lite only meaningfully for slimmable models. Disable NAM/IR bypass, start Audio with low output. Gate at -81 is off. Six knobs control input, gate, bass, mid, treble, output. Preset changes while running swap rigs with a brief fade, not guaranteed gapless; audio hardware setting changes reopen streams. While stopped edits autosave without opening ALSA.

Effects toolbar opens individual dialogs; Enable illuminates icon yellow and unlocks controls. Turning off remembers values. Compressor PRE/POST, chorus mix/rate/depth, delay mix/time/feedback, reverb mix/decay (.3–5 s)/Dark-Bright-Neutral. Hi-Z has independent enable and four pickup profiles; use only for assumed low impedance passive pickup loading, not external buffer or high-Z input. Tuner mutes output; practice metronome requires audio on. Calibration uses first active capture metadata and ADC reference, applies explicit input gain; reference starts unknown and may be cleared after routing change. Do not assume missing metadata means invalid capture.

Library search, folders, favorites, import/move/rename, confirmed permanent deletion. Sidebars can be hidden/resized; custom amp artwork is visual only. Four slots save automatically. Browser layout stored locally.

## Optional cloud and power

--cloud enables experimental TONE3000 device OAuth; use personal publishable key, never secret key. Session persists in private tone3000-session.json; disconnect deletes it. Mock tests pass, actual reboot/login/download not yet independently verified. API terms apply; no official affiliation. Local audio never requires cloud. Original USB Companion cannot control this Linux rig.

Optional power menu: run bash rpi/install-poweroff.sh as service user and confirm; exact systemctl poweroff and reboot sudo privileges only, no general root access. Existing poweroff-only installs must rerun helper for reboot. Disable with bash rpi/install-poweroff.sh --disable. On LAN anyone with API access can invoke confirmed power actions. No physical power switching.

No Pisound button or hotspot is installed by the general installer.

## Update and troubleshoot

```sh
cd ~/RPiT3K
sudo systemctl stop rpit3k-general
git pull --ff-only origin rpi-general
cmake --build build-rpi -j2
ctest --test-dir build-rpi --output-on-failure
./build-rpi/rpit3k --bypass --verify
sudo systemctl start rpit3k-general
```

Run sequentially and stop on failures. Service restarts with audio OFF. If audio fails check browser logs, aplay -l, arecord -l, sudo journalctl -u rpit3k-general -n 100 --no-pager. Increase period size/count if xruns; counter includes suspend recoveries, nominal per-direction buffer not round-trip latency. Audio OFF means no valid live meters; controller can be healthy without audio. 

Data lives in ~/.local/share/rpit3k-general. Back up privately, including library/settings/presets/favorites/artwork; OAuth file contains secrets, never share. Uninstall by disabling power helper (if enabled), disabling/stopping service, removing service unit and reloading systemd; preserve data unless deliberately deleting it.  No commercial models provided. See technical guide for licenses and current test limitations.
