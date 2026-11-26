# RPi-Ton3K — Blokas Pisound user guide

See [overview](README.md), [technical guide](rpi/README.md) and [validation](docs/DAISYSP_VALIDATION.md). 64-bit Raspberry Pi OS Lite with compatible Pisound; Pi 5 developer-tested, Pi 4/CM4/400 candidate, older Pi experimental. 32-bit and Pisound Micro not supported by this installer.

## Install

Normal sudo-enabled user, not root. Reliable power/cooling, preferably 2 GB or more RAM for compiling. Stop competing audio programs and lower monitor volume. Power off before attaching Pisound. Follow Blokas driver installation if necessary.

```sh
sudo apt update
sudo apt install -y git
git clone --branch rpi-ui https://github.com/tinker-net/RPiT3K.git
cd RPiT3K
# If Blokas driver is not installed:
bash rpi/install-pisound.sh --install-blokas
# Reboot, reconnect, then:
# cd ~/RPiT3K
bash rpi/install-pisound.sh
```

The optional Blokas step downloads the vendor's current unpinned installer and exits; reboot before running normal installation. Confirm aplay -l and arecord -l show Pisound. Pi 5 initial 64×3, Pi 4 128×3, older Pi 256×3. Fixed left capture/dual mono playback.

Installer installs dependencies, pins NAM Core, compiles, runs CTest and offline verification, installs/enables rpit3k.service. Existing settings/data preserved; initial buffer/routing flags do not overwrite existing settings. New readiness check verifies controller available **with audio stopped**, not ALSA streaming. Fresh installer not yet independently tested. --jobs 1 reduces build memory use. For updates stop service first.

## Access

Default loopback HTTP; SSH tunnel from another computer:
```sh
ssh -N -L 8080:127.0.0.1:8080 USER@HOST
```
Open http://localhost:8080. Explicit --lan at install exposes unauthenticated HTTP to the trusted isolated LAN, including library and cloud/power access. Never expose to Internet/untrusted network. For existing build use bash rpi/install-service.sh --lan; repeat --button/--cloud if desired.

## First use

Audio starts OFF every time. Last preset is selected, not playing. Import your own .nam and mono WAV IRs (up to 1 s after resampling to 48 kHz); use either NAM slot or both serially, optionally two parallel IRs. Choose Full/Lite only meaningfully for slimmable models. Enable the desired Pedal, Amplifier and IR stages, then start Audio with low output. Gate at -81 is off. Six knobs control input, gate, bass, mid, treble, output. Preset changes while running swap rigs with a brief fade, not guaranteed gapless; audio hardware setting changes reopen streams. While stopped edits autosave without opening ALSA.

Effects toolbar opens individual dialogs; Enable illuminates icon yellow and unlocks controls. Turning off remembers values. Compressor PRE/POST, chorus mix/rate/depth, delay mix/time/feedback, reverb mix/decay (.3–5 s)/Dark-Bright-Neutral. Hi-Z has independent enable and four pickup profiles; use only for assumed low impedance passive pickup loading, not external buffer or high-Z input. Tuner mutes output; practice metronome requires audio on. Calibration uses only the selected Amplifier (NAM 2) metadata and ADC reference, applies explicit input gain; nominal +1.14 dBu reference is an estimate at minimum analog gain, not measured for your hardware. Do not assume missing metadata means invalid capture.

Library search, folders, favorites, import/move/rename, confirmed permanent deletion. Sidebars can be hidden/resized; custom amp artwork is visual only. Four slots save automatically. Browser layout stored locally.

## Current shared controls and library

- **Pedal (NAM 1):** independent stomp with a 10 ms transition; its state is saved per preset. **Amplifier (NAM 2):** separate bypass. **Bypass IR:** disables both cabinet IRs, including a legacy WAV in slot 2. Captures remain selected and can be re-enabled. Structural changes use the existing live exchange and short fade; no gapless/spillover guarantee.
- **Input calibration:** uses only the selected Amplifier NAM and its selected slimmable child/root metadata, never the Pedal. Applies the global pre-pedal input gain explicitly; no automatic inter-stage calibration. No amplifier or valid metadata/reference means no automatic correction. The amplifier remains the reference even when bypassed.
- **Six knobs:** prominent 0–10 position plus editable technical dB underneath. Input 5 = unity, output 5 = half amplitude (about -6.02 dB), EQ 5 = 0 dB; gate OFF is the -81 sentinel. The scale is linear in the existing parameter, not a new gain curve. Input 0 and output 0 are silence. Drag normally, Shift-drag for 10× lower sensitivity, wheel for increments; focus/double-click the dB readout, Enter/blur to apply, Escape to cancel. Existing parameter ranges and quantization remain (input amplitude 0–2, step 0.000001; output 0–1, step .01; gate/EQ integer dB). Display rounding is not a new preset format.
- **Capture picker:** search filenames and folders using unordered AND terms, abbreviation expansion (FNDR/Fender, MRSHL/Marshall, BFSR/Super Reverb, CLN/Clean, WRM/Warm, etc.), inferred family tags and relevance sorting. Examples: `fender clean fat`, `marshall crunch`, `blackface warm`. Quick filters vary by Pedal, Amplifier and IR; Favorites narrows results. Classification is heuristic, not audio analysis. Optional **Index metadata** reads local NAM metadata sequentially while audio is stopped; results are browser-session cached, not persisted. Closing the picker stops further indexing. A2 matching depends on available text/metadata; architecture alone does not establish model generation.
- **Notifications:** contextual toast stack, success/info 3 s, warnings 6 s, errors and progress until dismissed/replaced (maximum five visible per stack). Dialog validation and ongoing import/cloud progress remain inline. No persistent Rig Details message.
- **Artwork:** custom family-named WebP (maximum 2 MiB); Rams Head, Kingsley Page, Twin Bender and Octavio families included. Import `ramshead.webp`, `kingsleypage.webp`, `twinbender.webp`, `octavio.webp` for custom images; no commercial images or captures supplied. Selection stored locally per capture.
- Shared UI changes require no native rebuild. For source installations pull the correct branch, restart its service and hard-refresh the browser; audio restarts OFF. Rebuild and run regression tests whenever native code/dependencies change.

## Optional cloud and power

--cloud enables experimental TONE3000 device OAuth; use personal publishable key, never secret key. Session persists in private tone3000-session.json; disconnect deletes it. Mock tests pass, actual reboot/login/download not yet independently verified. API terms apply; no official affiliation. Local audio never requires cloud. Original USB Companion cannot control this Linux rig.

Optional power menu: run bash rpi/install-poweroff.sh as service user and confirm; exact systemctl poweroff and reboot sudo privileges only, no general root access. Existing poweroff-only installs must rerun helper for reboot. Disable with bash rpi/install-poweroff.sh --disable. On LAN anyone with API access can invoke confirmed power actions. No physical power switching.

Optional single-click preset cycle: bash rpi/install-service.sh --button (add desired --lan/--cloud). Backs up /etc/pisound.conf and replaces CLICK_1 only; physical button still needs validation. Optional NetworkManager fallback: bash rpi/install-hotspot.sh, enter WPA2 password; requires LAN mode, SSID RPiT3K at 10.42.0.1, activates without other connectivity. Disable timer and connection with sudo systemctl disable --now rpit3k-hotspot.timer and sudo nmcli connection down RPiT3K-fallback.

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
