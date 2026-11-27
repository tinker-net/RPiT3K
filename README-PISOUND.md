# RPi-Ton3K — Blokas Pisound user guide

See [overview](README.md), [technical guide](rpi/README.md) and [validation](docs/DAISYSP_VALIDATION.md). 64-bit Raspberry Pi OS Lite with compatible Pisound; Pi 5 developer-tested, Pi 4/CM4/400 candidate, older Pi experimental. 32-bit and Pisound Micro not supported by this installer.

## Install

Normal sudo-enabled user, not root. Reliable power/cooling, preferably 2 GB or more RAM for compiling. Stop competing audio programs and lower monitor volume. Power off before attaching Pisound. Follow Blokas driver installation if necessary.

```sh
sudo apt update
sudo apt install -y git
git clone --branch main https://github.com/tinker-net/RPiT3K.git
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
ssh -N -L 8080:127.0.0.1:80 USER@HOST
```
Open http://localhost:8080 through the SSH tunnel, or http://HOST (including .local hostname) or http://LAN_IP directly in LAN mode (port 80). Use hostname -I to find the address; hotspot access is http://10.42.0.1. Existing source installations can migrate without changing their configuration using `bash rpi/migrate-http-port.sh`. Explicit --lan at install exposes unauthenticated HTTP to the trusted isolated LAN, including library and cloud/power access. Never expose to Internet/untrusted network. For existing build use bash rpi/install-service.sh --lan; repeat --button/--cloud if desired.

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

## Live button response (2026-11-26)

The physical mappings remain unchanged. The local helper requests compact responses rather than scanning the capture library. Browser meter polling also carries a lightweight button state, so changes can be reflected on the next approximately 80 ms poll instead of the 2 s full status cycle. Preset identification flashes no longer hold the action lock. Journal entries `BUTTON stomp lock_ms=... action_ms=...` and `BUTTON next ...` measure server-side dispatch, not physical gesture or analog response. The upstream Blokas daemon uses a 400 ms multi-click recognition timeout; installed versions may differ. Structural preset changes still prepare a new rig; no preloading or measured hardware latency is claimed.

Update an existing source install without changing its network/service configuration:

    git pull --ff-only origin rpi-ui
    sudo install -m 755 rpi/pisound-button.sh /usr/local/bin/rpit3k-button
    sudo systemctl restart rpit3k.service pisound-btn.service

Audio starts OFF after restart. Hard-refresh the browser.

### Capture artwork persistence

Manual pedal and amplifier appearance assignments are saved on the controller in `appearance.json`, keyed by capture library path. Existing browser assignments are imported when the browser reconnects (server choices take priority). Automatic is an explicit saved choice. No audio restart is required to change appearance.

## Development preview

Experimental branch only. Practice Mode replaces the amp view without changing the guitar chain. Separate practice-tracks directory; imports up to 256 MiB per track; HTTP range streaming to browser audio (not PiSound mixing). Browser-dependent codec and pitch-preserving playback rate. Space starts playback and toggles pause/resume. The dedicated Stop control returns to the selected reference point. A/B loop uses browser time events, not sample-accurate. No waveform, pitch shifting, recording, or MIDI yet. Smart names are reversible display-only filename expansions; unknown tokens preserved, original path retained. No persistent metadata index yet.

Offline backup: stop rpit3k.service, run as data owner `python3 rpi/data_backup.py backup ~/ton3k-backup.tar.gz`, restart service. Restore with `python3 rpi/data_backup.py restore ~/ton3k-backup.tar.gz` while service stopped; previous data retained. Includes all user data, not OS configuration or binaries. Do not migrate to DEB without checking data path.

### Native Practice Mode (experimental)
Install `ffmpeg` (includes ffprobe; needs rubberband filter for pitch shifting). Rebuild native engine. Stereo decoded audio feeds a bounded nonblocking pipe and mixes after guitar FX and metronome. Waveform generated on demand and cached as 1200 peaks on disk. Speed .5–1.5, pitch ±12 semitones. Control changes restart decoder at estimated position; timing and A/B loops are not sample-accurate. No whole-track PCM buffer. Audio must be ON; tuner and engine stop stop playback. Browser sends controls only. Hardware xrun/latency validation pending.

### Practice resource isolation
On Linux with at least four allowed CPUs, the realtime engine thread is pinned to the highest allowed CPU; FFmpeg and ffprobe are confined to the other allowed CPUs, run with nice +10 and best-effort I/O priority 7. No boot/kernel changes. Set RPIT3K_AUDIO_AFFINITY=0 in the service environment to disable both affinity policies. Decoder and waveform analysis are guarded against overlap; stop acknowledgement prevents stale buffered samples from a previous track. Hardware validation still required. No hard CPU isolation from other system processes is claimed.

The Space key now toggles play/pause/resume; the separate Stop button returns to the selected waveform reference. Pause position is estimated from transport polling, not sample-accurate.

### Practice transport controls
Space play/pause/resume; Enter restart from selected reference; period stop; U clear selection; Home beginning; Left/Right jump 5 seconds (Shift 1 second); L loop. Drag waveform to select a loop, drag edges to adjust or inside to move; click/double-click to clear selection and place reference. Ctrl/Cmd-wheel or +/- zoom, pan slider scrolls visible range. Waveform remains the cached 1200-point envelope, so zoom enlarges existing data rather than adding sample detail. Transport timing remains approximate; changes may restart FFmpeg. Inspired by https://www.seventhstring.com/xscribe/faq3.html, with Space intentionally configured for resume.

### Smart Library model recognition
Catalog identities take precedence over incidental pedal words in amp captures. BLBM, BFBM and TWBM identify distinct Bassman variants. Unknown artwork uses existing family or generic fallback. Original files unchanged. Model codes and EQ terminology based on https://amalgamcaptures.com/how-it-works/ and the published amp catalog. Manual appearance overrides remain authoritative.

### Smart IR names
WAV-only parser, separate from NAM. York Audio YA-prefixed files (or York Audio folder) use a cab-pack catalog and suffix microphone codes; Mix numbers remain opaque. Amalgam-style cabinet/speaker/filter tokens are expanded conservatively. Original WAVs, phase/version/position suffixes and preset paths are unchanged. Sources: https://www.yorkaudio.co/ and individual pack pages, https://amalgamcaptures.com/how-it-works/. Unknown names retain original labels; no inference of microphone blends. No audio processing changes.

### Capture channels
Model-scoped channel aliases expand the channel slot immediately following a recognized model (optionally after its year) when followed by a known gain designation. Bassman Blonde/Blackface B = Bass, N = Normal; Fender reverb amps N/V = Normal/Vibrato; classic Marshall JU = Jumped, BR/B = Bright, N = Normal; Vox TB = Top Boost; Imperial R/L = Rhythm/Lead; Rockerverb C/D = Clean/Dirty; Phoenix I/II = channels I/II. Unknown codes remain intact. No WAV, original filename, preset or audio processing changes. Naming structure: https://amalgamcaptures.com/how-it-works/. Channel abbreviations beyond documented examples are conservative model-specific conventions and need checking against actual pack filenames.

### Structured smart library
Smart names use a common identity (title, details, searchable label, skin) with Amalgam NAM, Amalgam IR and York pack-specific interpretation. Channels are concise; numbered tonal variants retain numbers; A1/A2 and known model years are displayed. York M25-SH identifies the cabinet; Scott Henderson is displayed only for IRs in a dedicated Scott Henderson folder. Phase and stereo distinctions retained. Original paths remain unchanged. Unknown tokens are retained, not guessed. Run `node rpi/smart_ir_test.js [optional-inventory.txt]` for regression and inventory coverage. The module is kept in an isolated pure section of the self-contained HTML to avoid a new server endpoint or package dependency.

## Portable backup and clean recovery
In Audio settings & diagnostics, turn Audio OFF, then Download backup or Restore backup. Backups include library, presets, settings, favorites, appearance, artwork, practice tracks and trash. Version 1 tar.gz contains SHA-256 manifest; archive is verified before download and before replacement. Credentials, browser local storage, waveform cache and OS/network configuration are excluded. Restore replaces saved data, retains previous directory beside it, reloads controller with audio OFF; re-login to cloud if needed. Trusted LAN only; do not distribute commercial captures. Large backups require free disk space for archive and verification staging and browser download memory. 8 GiB expanded limit. Older unversioned archives are not accepted by this version; use previous offline helper to recover them separately.
Fresh SD: install 64-bit Raspberry Pi OS Lite, configure user/SSH/network, clone main as above, install Blokas driver and reboot if needed, then run `bash rpi/install-pisound.sh --lan --button --cloud` (trusted LAN only; omit optional flags if undesired). FFmpeg is installed automatically. Restore through settings with Audio OFF. Hostname, Wi-Fi, analog input gain and external service configuration are not portable. Check presets and low-volume audio before normal use.
Offline CLI (service stopped, normal service user): `python3 rpi/data_backup.py backup ~/ton3k.tar.gz`, `python3 rpi/data_backup.py verify ~/ton3k.tar.gz`, `python3 rpi/data_backup.py restore ~/ton3k.tar.gz`. Start service after completion. Test: `python3 rpi/data_backup_test.py`. Physical fresh-SD and full browser restore acceptance pending.

## Experimental Guitar Pro reader
Branch experimental/guitar-pro only. Install pinned local alphaTab assets using `sudo apt install npm` if needed, then `bash rpi/install-score-reader.sh`. Restart rpit3k.service and refresh browser. Open Practice > Score > Open GP. Files are read from the browser, not uploaded or persisted. Supports GP7/8 .gp and older .gp3/.gp4/.gp5/.gpx through alphaTab; choose track, notation and zoom. No MIDI playback or synchronization. Existing waveform and transport unchanged. No runtime internet access needed after dependency install. Browser acceptance with actual GP8 files pending. alphaTab MPL-2.0, Bravura SIL OFL; upstream https://github.com/CoderLine/alphaTab.
