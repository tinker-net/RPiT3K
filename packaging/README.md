# Debian packages — isolated editions

Debian 13 / Raspberry Pi OS Trixie 64-bit. Experimental until fresh hardware installation is verified.

| Artifact | Package | Source edition | Target |
| --- | --- | --- | --- |
| rpi-ton3k-pisound | rpi-ton3k-pisound | rpi-ui | Pi 5 / Cortex-A76 + original Blokas Pisound |
| rpi-ton3k-pi5 | rpi-ton3k | rpi-general | Pi 5 / Cortex-A76 with any supported ALSA device |
| rpi-ton3k-pi4 | rpi-ton3k | rpi-general | Pi 4 / Cortex-A72 |
| rpi-ton3k-arm64 | rpi-ton3k | rpi-general | portable ARM64 |
| rpi-ton3k-amd64 | rpi-ton3k | rpi-general | x86-64 |

Install only one variant. Packages conflict with each other and share application installation paths; data directories are separate. Stop AND disable any existing source service before installation. No automatic migration, no bundled personal captures, passwords, tokens or presets.

Builds use immutable source revisions listed in build-deb.sh, pinned NAM Core and Embedded v2.0.0. Both editions include the actual native engine, shared DaisySP library/source, Python modules, web UI and license notices. Build runs CTest, production bypass verification and Hi-Z regression. The staged binary is also verified. Generic package CI installs/reinstalls/removes in a container. Pisound CI verifies extracted contents, scripts and executable offline; this is not a physical installation test. Releases remain prereleases.

## Dedicated PiSound package

Prepare the official Blokas APT repository on the target (see https://blokas.io/pisound/docs/the-pisound-software/). The package declares the vendor pisound and pisound-btn dependencies; APT must have access to them. Follow the vendor setup for kernel/overlay support and reboot if required. Do not run remote installers silently as Debian maintainer scripts.

When migrating a source installation, also disable its fallback timer before installing the package: `sudo systemctl disable --now rpit3k-hotspot.timer` (only if previously installed). The existing NetworkManager profile is retained.

With the dedicated artifact extracted:

    sudo apt install ./rpi-ton3k-pisound_*.deb

On the booted target the package configures and enables rpi-ton3k-pisound.service, installs the six physical button mappings in /etc/pisound.conf (previous mappings backed up), sets up a fallback NetworkManager hotspot and timer, and grants the dedicated service user only the two exact sudo power commands. Audio starts OFF, fixed hardware PCM hw:CARD=pisound,DEV=0, 48 kHz, left input/dual mono output, initial 64 x 3 and nominal ADC reference +1.14 dBu. Web profile exposes HTTP port 80 on the trusted LAN and enables optional cloud login. WARNING: unauthenticated API including power actions; never expose to the Internet or untrusted network. Change BIND in /etc/default/rpi-ton3k-pisound to 127.0.0.1 for SSH-only access.

| Gesture | Action |
| --- | --- |
| Click 1 | NAM 1 stomp |
| Click 2 | Next preset, one confirmation flash |
| Click 3 | Hotspot toggle |
| Hold 1 s | Identify preset with 1–4 flashes |
| Hold 3 s | Audio on/off, one confirmation flash |
| Hold 5 s | Vendor shutdown |

Hotspot RPiT3K, http://10.42.0.1, only when disconnected or manually enabled. Existing RPiT3K-fallback profile is reused without changing credentials. A new profile uses a unique generated WPA2 password: sudo cat /var/lib/rpi-ton3k-pisound-integration/hotspot-password (do not share it). Existing profile credentials are not copied. The timer does not intentionally interrupt working network connections. Manual OFF inhibits automatic fallback until reboot/manual ON.

Data: /var/lib/rpi-ton3k-pisound. Migration is manual with both source and package services stopped; back up ~/.local/share/rpit3k, copy only the desired library/settings/presets/favorites/artwork and set owner rpi-ton3k-pisound. Do not copy credentials into a distributable package. Remove with sudo apt remove rpi-ton3k-pisound; removal on a booted system restores replaced button mappings, removes package-owned hotspot and power permission, retains personal data. Source service is not re-enabled automatically. If configured in a chroot, boot the target and run sudo dpkg-reconfigure rpi-ton3k-pisound. Pi 4 Pisound package is not produced yet.

## Generic packages

    sudo apt install ./rpi-ton3k_*.deb

Install a single CPU variant. No Pisound driver dependency, button mapping/helper, hotspot unit, network provisioning or sudo power permission is shipped. Default localhost:8080, cloud disabled, configurable PCM/channel routing, 256 x 3, unknown ADC reference, audio OFF. Use SSH forwarding or explicitly configure trusted LAN access. Data /var/lib/rpi-ton3k survives removal/purge. Remove with sudo apt remove rpi-ton3k.

## Local build

From deb-packaging with git, build-essential, cmake, libasound2-dev, python3, dpkg-dev and ca-certificates:

    bash packaging/build-deb.sh 0.1.0~preview1 cortex-a76 pisound
    bash packaging/build-deb.sh 0.1.0~preview1 cortex-a76 general

The first command is ARM64 only. Generic CPU argument can be empty for portable ARM64/AMD64 or cortex-a72 for Pi 4. Update source pins deliberately when promoting a new tested edition. The generic source pin is its existing branch revision; it does not automatically inherit newer Pi-only UI changes. See build-provenance in installed documentation.

[Build artifacts](https://github.com/tinker-net/RPiT3K/actions/workflows/deb-packaging.yml) · [Prereleases](https://github.com/tinker-net/RPiT3K/releases) · [Pisound source guide](https://github.com/tinker-net/RPiT3K/blob/rpi-ui/README-PISOUND.md).

## Current shared controls and library

- **Pedal (NAM 1):** independent stomp with a 10 ms transition; its state is saved per preset. **Amplifier (NAM 2):** separate bypass. **Bypass IR:** disables both cabinet IRs, including a legacy WAV in slot 2. Captures remain selected and can be re-enabled. Structural changes use the existing live exchange and short fade; no gapless/spillover guarantee.
- **Input calibration:** uses only the selected Amplifier NAM and its selected slimmable child/root metadata, never the Pedal. Applies the global pre-pedal input gain explicitly; no automatic inter-stage calibration. No amplifier or valid metadata/reference means no automatic correction. The amplifier remains the reference even when bypassed.
- **Six knobs:** prominent 0–10 position plus editable technical dB underneath. Input 5 = unity, output 5 = half amplitude (about -6.02 dB), EQ 5 = 0 dB; gate OFF is the -81 sentinel. The scale is linear in the existing parameter, not a new gain curve. Input 0 and output 0 are silence. Drag normally, Shift-drag for 10× lower sensitivity, wheel for increments; focus/double-click the dB readout, Enter/blur to apply, Escape to cancel. Existing parameter ranges and quantization remain (input amplitude 0–2, step 0.000001; output 0–1, step .01; gate/EQ integer dB). Display rounding is not a new preset format.
- **Capture picker:** search filenames and folders using unordered AND terms, abbreviation expansion (FNDR/Fender, MRSHL/Marshall, BFSR/Super Reverb, CLN/Clean, WRM/Warm, etc.), inferred family tags and relevance sorting. Examples: `fender clean fat`, `marshall crunch`, `blackface warm`. Quick filters vary by Pedal, Amplifier and IR; Favorites narrows results. Classification is heuristic, not audio analysis. Optional **Index metadata** reads local NAM metadata sequentially while audio is stopped; results are browser-session cached, not persisted. Closing the picker stops further indexing. A2 matching depends on available text/metadata; architecture alone does not establish model generation.
- **Notifications:** contextual toast stack, success/info 3 s, warnings 6 s, errors and progress until dismissed/replaced (maximum five visible per stack). Dialog validation and ongoing import/cloud progress remain inline. No persistent Rig Details message.
- **Artwork:** custom family-named WebP (maximum 2 MiB); Rams Head, Kingsley Page, Twin Bender and Octavio families included. Import `ramshead.webp`, `kingsleypage.webp`, `twinbender.webp`, `octavio.webp` for custom images; no commercial images or captures supplied. Selection stored locally per capture.
- For package installations update via the matching .deb artifact, not git pull; restart the package service if needed and hard-refresh the browser. Audio restarts OFF.


## Latest validation

[Five-variant package CI passed at 8ab4841](https://github.com/tinker-net/RPiT3K/actions/runs/45853780731), using source pins 0275920 (PiSound) and 37952ec (General). Physical installation and browser/ALSA tests are not established by this run. See the [current project state and acceptance checklist](https://github.com/tinker-net/RPiT3K/blob/rpi-ui/docs/PROJECT_STATE.md). Documentation-only commits do not change the functional source pins.

## Experimental PiSound package (Practice)
On experimental/guitar-pro the PiSound build uses HEAD (or explicit RPIT3K_SOURCE_REF) and bundles FFmpeg dependency, score assets and new modules. Requires npm at build time. The dedicated service stores data in /var/lib/rpi-ton3k-pisound/data; the previous package roots are copied on first upgrade and retained. For source migration export a verified backup in Settings, stop and disable source service and hotspot timer, install matching DEB and restore through Settings with Audio OFF. Do not delete the source data until physical acceptance. No automatic root-level installation via LAN web UI; Settings displays version and links releases. Generic edition pins unchanged. Experimental workflow uploads DEB only if build checks pass; no public release yet.
