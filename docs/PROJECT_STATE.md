# RPiT3K — current project state

Updated 2026-11-26. Current source and validation scope, not a release certification.

## Maintenance
- rpi-ui: primary Pi 5/Pisound source edition; rpi-general: same shared features with configurable ALSA and separate data/service. Keep both in sync, preserve hardware differences. No new branches without maintainer request.
- live-rig is historical; deb-packaging is not maintained by this change and must not be presented as synchronized. Original Daisy firmware, hardware and app are separate inherited upstream components.
- [User guide](../README-PISOUND.md), [technical architecture](../rpi/README.md), [historical engine measurements](ENGINE_VALIDATION_2026-11-25.md), [current DaisySP evidence](DAISYSP_VALIDATION.md).

## Current evidence
Pi 5/Pisound, aarch64 Linux 6.18.60+rpt-rpi-2712, GCC 14.2.0: incremental build and 8/8 CTest PASS at bf454958beece27f884513d0f9ff7b7f9d06270a, 3.48 s. 24/24 calibrated RT60 points; max absolute error .04174815 s, relative .06388795; compressor max curve error .004901886 dB; integer delay echo timing exact in tested cases; chorus modulation/bypass tested; 8 mocked OAuth and 5 effect state tests. Combined synthetic FX automation 10 s processed in .09209452 s; not ALSA timing. Native IR max absolute error 3.97309e-7, tuner max 2.66869 cents. Historical 16/16 hybrid null tests and short live Pi runs are older evidence, not retested at this HEAD.

## Current behavior
- Audio always OFF at service start. Persistent four slots, independent NAMs, two parallel IRs, live worker exchange with fade/reset (not gapless); invalid replacement preserves old rig.
- Input-keyed expander, EQ and gains, optional Hi-Z and explicit first-active NAM calibration, native DaisySP compressor/chorus/delay/ReverbSc, practice metronome and tuner.
- Single web skin, independent collapsible sidebars, library folders/favorites and artwork, effect switches with remembered values, device controls and optional power menu. OAuth saved in private file, cloud disabled by service installers unless explicitly enabled.
- New consolidation fixes installer readiness to require controller available and audio stopped; no unattended live audio test. Power helper allows exact poweroff/reboot commands only after explicit opt-in. Existing installations must rerun helper to grant reboot. Production-chain regression passed on Pi 5 (0.08 s, max blend residual 1.3981e-7); updated CI checks not independently verified.

## Open validation
Clean SD installation, real browser rendering, live audio stability/latency and audible transitions with latest effects, hardware button/hotspot, real OAuth authorization/download/restart/reboot, generic USB/x86 hardware, and physical ADC/Hi-Z measurement. Documentation and code inspection do not establish these results. No changes to DSP algorithms in documentation consolidation.

## Independent cabinet and second NAM bypass
Each preset stores independent `bypass_nam2` and `bypass_ir` switches; NAM 1 retains its existing stomp. IR bypass excludes both cabinet IRs including legacy WAV in slot 2. Structural changes use the existing live rig exchange and fade, without reopening ALSA. Legacy global bypass migrates to NAM 1 OFF and both bypass switches ON. No inference or convolution algorithm changes. Added controller routing/migration and production offline signal checks; CI and hardware verification pending.
