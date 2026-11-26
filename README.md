# RPi-Ton3K — Native NAM guitar processor for Linux

**Independent open-source project · experimental generic ALSA edition · C++20 / ALSA · MIT project code, third-party licenses apply**

RPiT3K is inspired by the [TONE3000 × Daisy DIY Pedal](https://github.com/tone-3000/t3k-diy-pedal). It is a standalone, browser-controlled guitar rig, not a general-purpose plugin host or a port of the microcontroller binary. Local playing works offline. No JACK, PipeWire or LV2 host required.

## Choose your edition

| Branch | Hardware | Service | Default initial buffering |
|---|---|---|---|
| [rpi-ui](https://github.com/tinker-net/RPiT3K/tree/rpi-ui) | Raspberry Pi + Blokas Pisound | rpit3k | Pi 5: 64 × 3 |
| [rpi-general](https://github.com/tinker-net/RPiT3K/tree/rpi-general) | 64-bit Debian/Ubuntu/Pi OS, configurable ALSA | rpit3k-general | 256 × 3 |

Both source editions share features; Pi 5 is the measured baseline, generic hardware remains experimental. Use separate checkouts/data; do not run both services on port 8080. Historical branches and Debian packaging are not guaranteed current.

## Features
- Two independent serial NAM slots, automatic compatible A2 Embedded/Core dispatch, Full/Lite selection, native .nam.
- Two parallel mono WAV cabinet IRs (up to 1 s at 48 kHz), full 64-sample partitioned convolution and blend.
- Input/output gain, input-keyed soft-knee expander, three-band EQ, optional Hi-Z model and explicit input-level calibration.
- Native DaisySP compressor (PRE/POST), chorus, delay, calibrated ReverbSc, individual enables and remembered values per preset.
- Four autosaved slots, live rig replacement without reopening ALSA for structural edits, short fades (not gapless).
- Chromatic tuner, practice metronome, input/output meters, CPU/temperature/buffer/xrun diagnostics.
- Browser library with folders, favorites, import, rename/move/delete; amp artwork, independent collapsible sidebars, fixed TONE3000-inspired interface.
- Audio starts OFF; optional trusted-LAN access, host shutdown/reboot, experimental TONE3000 device OAuth with persisted session. Original Daisy Companion is separate.

## Installation\n\nSee [General installation guide](README-GENERAL.md). Clone the appropriate branch and run its installer as a normal sudo-enabled user. Start audio explicitly in the browser. Do not expose unauthenticated HTTP to the Internet.

## Engineering evidence

| Measurement | Result | Scope |
|---|---|---|
| CTest | 8/8 PASS, 3.48 s | Pi 5, bf45495, 2026-11-26 |
| Reverb calibration | 24/24; max 41.75 ms / 6.39% errors | T30 estimates, synthetic |
| Compressor | max 0.004902 dB static error | synthetic DC curve |
| Delay | exact tested integer echo indices | 20–1000 ms, three feedback settings |
| Combined effects | 10 s in 92.095 ms | DSP-only automation, not ALSA deadline |
| IR convolution | max 3.97309e-7 absolute error | 1–48000 taps |
| Hybrid NAM | 16/16 null tests | earlier Pi build, tested captures |
| OAuth | 8/8 mock tests | no real server/reboot validation |

[Current effect validation](docs/DAISYSP_VALIDATION.md) · [Historical engine measurements](docs/ENGINE_VALIDATION_2026-11-25.md) · [Technical architecture and reproduction](rpi/README.md) · [Project state and open validation](docs/PROJECT_STATE.md).

No measured analog round-trip latency claim. Real-time results depend on captures, hardware, thermal conditions and buffering. Fresh installer, real OAuth and latest live hardware tests remain open. No current screenshot is claimed; archived screenshots may depict previous layouts.

## Upstream and licensing

Original [Daisy firmware](README-DAISY.md), [hardware](hardware/README.md) and [USB Companion](app/README.md) are retained for provenance, not Linux deployment instructions. Thanks to TONE3000, NAM Core, Blokas and Daisy Audio. RPiT3K is independent, not an official product. [MIT license](LICENSE); [DaisySP MIT and LGPL-2.1 source/license notices](rpi/vendor/daisysp/README.md); UI artwork notice [UI-TONE3000-LICENSE.txt](UI-TONE3000-LICENSE.txt). Capture and IR rights remain with their authors. Report bugs with commit, hardware, settings, steps and sanitized logs; no credentials or commercial captures.
