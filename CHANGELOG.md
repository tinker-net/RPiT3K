# Changelog

## PiSound source — 2026-11-26
- Faster physical controls, persistent artwork, offline backup/restore.
- Practice Mode: stereo FFmpeg, independent speed/pitch, waveform zoom and selection, A/B, keyboard transport; realtime CPU affinity and reduced decoder priority.
- Smart amp/model/channel and York/Amalgam IR names; DI hidden, CAB retained, original files unchanged.
- ARM/x86 and local Pi regression passed. Zero late blocks/xruns in reported windows; full stress pending. [Evidence and rollback](docs/PROJECT_STATE.md).

## Native 0.2 — development preview (2026-11-26)
- Persistent library references, folders and favorites.
- Background NAM/IR rig preparation and reduced UI refreshes.
- Experimental host sample-rate adapter with standalone continuity tests.
- Successful CI builds for macOS Universal, Windows x64, Linux x86-64 and ARM64.
- Real DAW verification pending; AU validation is not established.

## Native 0.1 — 2026-11-26
- First VST3/AU/LV2 platform builds, original web interface embedded in JUCE.
- Cubase on Apple Silicon: GUI and initial audio confirmed by user.
- 48 kHz only; incomplete library and UI controls.

## Debian preview 54 — 2026-11-26
- Five variants: PiSound Pi 5 and Standalone Pi 5/Pi 4/ARM64/AMD64.
- Independent pedal/amp/IR bypass, calibration, musical knobs and capture search.
- Automated package tests passed; physical package installation pending.
- [Published packages and notes](https://github.com/tinker-net/RPiT3K/releases/tag/deb-preview-54).
