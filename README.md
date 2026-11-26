# RPi-Ton3K — Debian packages

This branch packages the native Linux editions of Ton3K for Debian 13 / Raspberry Pi OS Trixie 64-bit. The package builds use pinned revisions of the source branches; packaging is kept separate from the audio engine.

| Artifact | Source | Target |
| --- | --- | --- |
| rpi-ton3k-pisound | rpi-ui | Pi 5 / original Blokas Pisound |
| rpi-ton3k-pi5 | rpi-general | Pi 5 / generic ALSA |
| rpi-ton3k-pi4 | rpi-general | Pi 4 / generic ALSA |
| rpi-ton3k-arm64 | rpi-general | portable ARM64 |
| rpi-ton3k-amd64 | rpi-general | x86-64 |

The dedicated package installs the Pisound button mappings, hotspot fallback, fixed ALSA configuration and power controls. The other four artifacts deliberately omit board-specific integration. All editions boot with audio stopped. The dedicated package requires the official Blokas APT repository and supported Pi kernel. Personal libraries, credentials and presets are not distributed.

[Installation and migration guide](packaging/README.md) · [GitHub Actions](https://github.com/tinker-net/RPiT3K/actions/workflows/deb-packaging.yml) · [Experimental releases](https://github.com/tinker-net/RPiT3K/releases)

[PiSound source edition](https://github.com/tinker-net/RPiT3K/tree/rpi-ui) · [Generic source edition](https://github.com/tinker-net/RPiT3K/tree/rpi-general) · [Engineering evidence](https://github.com/tinker-net/RPiT3K/blob/rpi-ui/docs/PROJECT_STATE.md)

Packages are experimental until installation, upgrade and real audio operation are confirmed on target hardware. Offline CI tests do not establish ALSA timing or physical button operation. Install only one matching package; see the guide for source service migration and trusted-network access.

Independent open-source project inspired by TONE3000 × Daisy. MIT project code; third-party notices and DaisySP source are included in the packages.
