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


## Extended ARM64 characterization — measured 2026-11-26

Source: user-provided terminal log validation-daisysp-extended.log, HWW-RPiT3K, rpi-ui 502e38b76e8e4ace2dfb87f3388913de68d2ee42. Incremental build including characterization target successful. CTest 6/6 PASS, 0 failures, total 1.92 s. Existing four regression groups unchanged (0.00, 0.06, 0.30, 0.02 s); characterization 1.18 s; OAuth group 0.34 s (eight unittest cases in 0.172 s). CMake 3.31 warns about deprecated FetchContent_Populate(t3kembedded), nonfatal.

### Compressor
All 15 static DC points pass. Input levels -60/-40/-24/-12/-6 dBFS:
| Amount | Threshold dBFS | Ratio | Measured outputs dBFS |
|---|---:|---:|---|
| .25 | -18 | 2.25 | -60 / -40 / -24 / -15.33718 / -12.67064 |
| .50 | -24 | 3.5 | -60 / -40 / -24.00448 / -20.5762 / -18.86199 |
| 1 | -36 | 6 | -60 / -40 / -34.0049 / -32.00464 / -31.00401 |

Maximum absolute static curve error 0.004901886 dB (tolerance 0.5 dB). Gain during rising step at 5 ms/50 ms/1 s: -16.18971/-24.98497/-24.98548 dB; falling step at 150 ms/750 ms/2 s: -17.89001/0/0 dB. These are measured step responses, not independently fitted attack/release time constants.

### Delay
All 12 combinations (20/100/350/1000 ms, feedback 0/.35/.85) pass. First echoes at 960/4800/16800/48000 samples; subsequent echoes at exact integer multiples. Identical amplitude sequences for all four times, input impulse .5, mix .5:
| Feedback | Echo 1 | Echo 2 | Echo 3 |
|---:|---:|---:|---:|
| 0 | .2499964 | 8.407791e-44 | 0 |
| .35 | .2499964 | .08749875 | .03062456 |
| .85 | .2499964 | .2124934 | .1806163 |

Maximum absolute amplitude error .0000087 (rounded logged values); off-index energy criterion passed. Does not characterize fractional delay or maximum discontinuity while changing time.

### Chorus
Zero-depth impulse: delay 576 samples (12 ms).
| Wrapper mix | Dry impulse | Delayed impulse |
|---:|---:|---:|
| .25 | .4375009 | .06249911 |
| .50 | .3750018 | .1249982 |
| 1 | .2500036 | .2499964 |

Modulation .5 Hz: observed lag 291–854 samples; recurrence mean error .1 sample. 2 Hz: observed lag 330–770 samples; recurrence mean error .03636364 sample. Sparse impulse sampling does not determine exact continuous extrema. Mix 100% intentionally yields upstream ChorusEngine 50/50 blend. Exact bypass recovery passes.

### ReverbSc
T30 extrapolated RT60, first-difference-energy ratio (brightness proxy), and total impulse energy:
| Voice | Requested s | RT60 s | Brightness | Energy |
|---|---:|---:|---:|---:|
| Dark | .2 | .2983129 | .6067853 | .00005534589 |
| Dark | 1.5 | 1.4231 | .382298 | .003546281 |
| Dark | 5 | 4.690807 | .2230183 | .009732536 |
| Bright | .2 | .2985754 | 1.09064 | .0001122822 |
| Bright | 1.5 | 1.435634 | .7770095 | .007279516 |
| Bright | 5 | 4.739346 | .5099261 | .01996665 |
| Neutral | .2 | .3010704 | .8498453 | .00008224736 |
| Neutral | 1.5 | 1.428496 | .5705739 | .005244294 |
| Neutral | 5 | 4.718306 | .3536531 | .01422334 |

Monotonic decay and brightness ordering confirmed; minimum requested .2 s measures ~.30 s, so do not claim calibrated RT60. No changes to DSP or tolerance in this documentation commit. Brightness proxy is not a frequency response measurement.

### Combined automation and performance
10 seconds / 480000 samples synthetic signal and parameter changes: 0.09216136 s elapsed, 0.9216136% of audio duration (~108.5x realtime), peak .4476328, energy checksum 3626.6. DSP-only wall clock, not per-block worst-case timing, CPU utilization, or end-to-end ALSA latency. Finite output and bounded peak pass; audible click-free switching not established.

### OAuth
All eight mocked tests PASS: corrupt file, disconnect, expired without refresh, invalid grant, network failure keeps session, refresh rotation persists, refresh without rotation, restart and permissions. No real OAuth server or reboot tested.

### Remaining
Real service restart/reboot OAuth, real NAM/IR/preset and audio-device testing, listening/recording, xrun and per-block deadline validation, clean build, and independent generic ALSA hardware validation remain open. No new branches.
