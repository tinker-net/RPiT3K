# DaisySP native effects — validation record

## Hardware baseline, 2026-11-26

User-supplied terminal output, HWW-RPiT3K (Raspberry Pi 5/Pisound edition, aarch64), commit `cba64aaf162fe27550072bb7a128b362c3c9a297`, Linux 6.18.60+rpt-rpi-2712, Debian GCC 14.2.0-19. Incremental build completed all targets; CTest 4/4 passed, zero failures, 0.38 s total. This is measured evidence, not a clean build or an audio-device test.

| Test | Result | Time (s) |
|---|---|---:|
| practice_metronome | PASS: timing, gain, mute, bypass | 0.00 |
| capture_calibration | PASS: 3 unit tests | 0.06 |
| native_dsp | PASS: Hi-Z, native FX, expander, IR, tuner | 0.30 |
| live_rig_exchange | PASS: 20 hot exchanges and invalid-rig retention | 0.02 |

| IR samples | Maximum absolute error |
|---:|---:|
| 1 | 4.71026e-09 |
| 63 | 1.20995e-07 |
| 64 | 9.85991e-08 |
| 65 | 9.9702e-08 |
| 4096 | 3.17334e-07 |
| 24000 | 3.93376e-07 |
| 48000 | 3.97309e-07 |

Tuner input Hz / measured Hz / error cents: 41.2034/41.204/0.0239398; 82.4069/82.4135/0.137856; 110/110.006/0.100916; 146.832/146.872/0.465735; 196/196.047/0.41601; 246.942/247.126/1.29207; 329.628/330.137/2.66869; 440/440.403/1.58468.

Native FX aggregate test verifies initial exact bypass, compressor attenuation/recovery, three reverb voicings' impulse energy/decay, 100 ms delay impulse, chorus modulation. It does not characterize effect parameters or verify complete live audio routing.

## Source and signal chain

See [upstream sources and licenses](../rpi/vendor/daisysp/README.md). Compressor and ReverbSc: LGPL-2.1, pinned c89d380c62620d6fee9105c5035e081c9b7ea843. ChorusEngine and DelayLine: MIT, pinned a0494a3adb67f549e18dfd71a35fa656f65b38b6. Vendored upstream code unchanged. Wrapper settings and mix laws are RPiT3K design choices, not upstream factory presets.

Mono, 48 kHz: input-keyed gate detector, Hi-Z/input gain, PRE compressor, NAM A/B, parallel IR blend, EQ, gate gain, POST compressor, chorus, delay, ReverbSc, output gain/clamp. Tuner mutes guitar; metronome mixed separately. Compressor amount maps threshold -12 to -36 dBFS and ratio 1:1 to 6:1, attack .005 s, release .15 s, no makeup. ChorusEngine uses 12 ms base delay, depth internally clamped to .93, rate .1–5 Hz, internal 50/50 dry/delayed mix (so wrapper 100% is not wet-only). Delay 20–1000 ms, feedback 0–.85, fractional interpolation, smoothed time. ReverbSc stereo output averaged to mono, cutoff 3800/10000/6200 Hz (Dark/Bright/Neutral); approximate decay feedback from 60 ms mean delay, not calibrated RT60. Effects bypass after ramp; internal tails are drained but wet signal is faded when disabled, not audible spillover.

## Extended automated characterization — pending execution

`daisysp_characterization` compiles against production wrappers and vendored sources, at 48 kHz. `tonecloud_session` uses temporary directories and mock OAuth only. The new tests have NOT yet been executed on the device; thresholds are prospective engineering acceptance criteria, not measured results.

| Area | Measurement and acceptance |
|---|---|
| Compressor | DC static curve at three amounts and five levels; error <0.5 dB; step attack/release gain at specified times, monotonic recovery; exact bypass |
| Delay | Impulses at 20/100/350/1000 ms, feedback 0/.35/.85, first three echoes at exact sample indices; amplitude tolerance .0002; off-index energy <1e-8; bypass |
| Chorus | Zero-depth impulse at 576 samples, dry/wet levels with three mixes; 0.5/2 Hz modulation via repeated impulse peak positions, range and recurrence; bypass |
| Reverb | Impulse at three requested decays for each voicing; backward-integrated energy (Schroeder), linear regression -5 to -35 dB extrapolated RT60; monotonic decay, spectral brightness proxy (first-difference energy / energy), bypass |
| Combined FX | 10 seconds synthetic signal with live parameter changes, finite output and bounded peak; wall-clock DSP-only processing time; no ALSA real-time claim |
| OAuth | Restart, 0600 permissions, rotated and unchanged refresh token, logout, invalid grant, transient network failure, malformed file, no refresh token |

Run:
```sh
cmake --build build-rpi -j2
ctest --test-dir build-rpi --output-on-failure -V
```

Record commit, kernel, compiler, all output and hardware separately. Never include OAuth credentials in logs.

## Hardware and listening validation still required

- Fresh build and full native regression on each edition. Generic ALSA not validated by Pisound results.
- Real guitar/NAM/IR playback, 64x3 at 48 kHz; compare xrun counter before/after each effect and all four simultaneously, report test duration, CPU and peak values; repeat with two NAMs and long IRs. CPU meter is whole-system utilization, not audio-thread deadline.
- Change effect parameters during sustained notes, toggle effects and swap presets while listening; document clicks, dropouts, tail behavior, perceived gain and clipping.
- Save/reload a preset and restart service; verify effect values, both NAMs, IRs, Hi-Z. Authorize TONE3000 once, restart service and then reboot, browse/download a capture without reauthorization; logout must clear persisted session. Check token file permissions using stat only, never cat.
- Offline recordings / spectrograms and listening comparisons; no claim of sonic quality or calibrated RT60 until measured. 
