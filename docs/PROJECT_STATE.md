# RPiT3K — Project state and continuity

Last reviewed: 2026-11-26. This is the canonical cross-branch handover, maintained on `rpi-ui` (stable development baseline, not GitHub's default branch). Read it before changing code. Detailed measurements remain in the branch-specific documentation.

## Evidence policy

- Implemented: verified in source at an identified revision.
- Validated: actual test evidence, with platform, configuration and scope; historical documented results are not fresh tests.
- Pending: hypothesis, planned work or unverified behavior. Never promote it to validated without evidence.
- User decisions and requests are not proof of implementation. Preserve existing behavior unless explicitly asked to change it. Update this file with material decisions, changes, regressions and test outcomes; record commit and test configuration. Do not silently merge, rename, delete or repurpose branches.

## Branch map (observed before this documentation commit)

| Branch | HEAD | Role |
|---|---|---|
| rpi-ui | 654dfd68717c374dea70eedf1521a927627b4fbc | Stable maintainer Pisound source baseline |
| rpi-general | f468bd64d17c5656e5c199da79bf4f6b442c7747 | General Linux ALSA deployment; experimental portability |
| deb-packaging | cbffb7dc10a7bd0a21783f4b49854426fb6ede1e | Experimental Debian packages |
| embedded-a76 | d95599e4ab573caa769145bd9b5e043b376d2a78 | Original hybrid backend development |
| main | f11d98a394d652addf27da0475e19d5ae410d32e | GitHub default; not the stable Pisound baseline |
| linux-native | 45de75bf79c4037e631f62da7d9124d6a2b2c5e3 | Existing branch; current role not audited |
| rpi-native | 096ba12408654bd7d01335018f12326dd2bbc685 | Existing branch; current role not audited |

## Architecture and invariants

Native C++20 ALSA duplex, 48 kHz, S32_LE, left input/dual mono output; default 64 frames × 3 periods. Selectable 64/128/256/512 frames and 2/3/4 periods. No JACK, PipeWire or LV2 required. Python web controller, four persistent presets, local NAM/WAV import and systemd. Preset switches restart audio, not gapless. Tuner mutes output. Preserve direct .nam loading, original capture library, sample-rate checks and continuous model state. NAM Core pinned to d3189ed482ded880c128bf312941266c4fa5ceec, float32 interface and A2 fast build. Native partitioned FFT convolution, 64-sample partitions, up to 48000 samples at 48 kHz; no automatic IR loudness normalization.

Hybrid backend: TONE3000 Embedded v2.0.0, engines/cortex-a76, A2 Full (8 channels) and Lite (3 channels), compatible mono 48 kHz models including eligible selected SlimmableContainer children. Core handles A1 and unsupported Embedded models. Core validation precedes dispatch; strict less-than slimmable breakpoint selection. Embedded processes chunks up to 64 frames with continuous state. RPIT3K_NAM_ENGINE=core forces Core; -DRPIT3K_EMBEDDED=OFF disables Embedded at build time. Logs identify NAM_ENGINE=embedded or NAM_ENGINE=core. CMake files in rpi-ui, rpi-general and deb-packaging select the same A76 source when enabled. No upstream PR submitted according to the existing technical report.

## Validation ledger (historical, documented in rpi/README.md)

Pi 5 + Pisound, 48 kHz, 64 frames, offline benchmark, three alternating runs per backend, no IR/effects, same executable, same captures. Core is the optimized A2-fast build.

| Case | Core median µs | Auto median µs | Speedup | Relative null residual |
|---|---:|---:|---:|---:|
| A2 Full | 147.002 | 55.081 | 2.669× | −94.07 dB |
| A2 Lite | 36.128 | 13.240 | 2.729× | −∞ (exact on test signal) |
| A1 | 273.436 | 273.505 | 1.000× | −∞ (exact on test signal) |
| A1 → A2 Full | 423.207 | 337.349 | 1.255× | −94.30 dB |

16/16 null tests passed at 64/128/256/512 frames; acceptance relative RMS residual ≤ −80 dB and max absolute error ≤ 1e-4, finite unclipped output and asserted routing. These are not universal bit-equivalence claims. Native DSP regression 1/1 and bypass passed. Short live A2 Full + two IRs run at 64×3: 13 five-second intervals, worst block 575.056 µs, zero late blocks, recoveries or clips; not a controlled backend comparison. Shared Pi results are not independent validation of other branches.

## Open question: x86/AMD64 Embedded

Confirmed in source: RPIT3K_EMBEDDED defaults ON and selects Cortex-A76 sources without a processor guard. RPIT3K_CPU tuning is ARM64-only. No dedicated x86 Embedded implementation/dispatch is established by this code. General installer accepts x86_64 and aarch64; Debian CI matrix includes amd64, arm64, Pi4 and Pi5. CI configuration is not proof of a successful run or live model inference. Actual x86 build status, scalar/SIMD path, selected runtime engine and performance remain to be verified; do not claim x86 is Core-only or that A76 Embedded cannot run there.

Next investigation (not yet authorized as a code change): inspect pinned upstream C implementation and package flags, CI run logs; build on x86 and check engine logs, run hybrid_test.py and compare forced Core vs auto; only then assess dedicated SIMD optimization. Preserve Pi baseline and isolate any experimental changes.

## Other pending work and recent user requests

- Long-session audio stability, broader capture coverage, controlled IR/dual-IR backend comparisons, physical ADC–DAC latency and input calibration/noise/headroom, other interfaces and Debian/x86 physical hardware validation.
- TONE3000 account integration is experimental and not end-to-end validated. Companion integration was withdrawn in recent conversation; do not reintroduce without explicit request.
- Recent UI requests: start with audio off; improve tuner and use tuning-fork icon; order tuner, explicit audio on/off and input calibration before power menu (shutdown/reboot). Implementation status of these specific requests was not audited for this document; inspect current code before changing anything.
- Historical UI tags mentioned: ui-classic-original and ui-tone3000-v1; verify refs before using them.

## Primary references

- [Stable technical report and reproducible tests](../rpi/README.md)
- [Build configuration](../rpi/CMakeLists.txt)
- [Hybrid dispatch](../rpi/hybrid_nam.h)
- [Hybrid test harness](../rpi/hybrid_test.py)
- [General installer](https://github.com/tinker-net/RPiT3K/blob/f468bd64d17c5656e5c199da79bf4f6b442c7747/rpi/install-general.sh)
- [Debian CI workflow](https://github.com/tinker-net/RPiT3K/blob/cbffb7dc10a7bd0a21783f4b49854426fb6ede1e/.github/workflows/deb-packaging.yml)

This review verified repository metadata, branch refs, CMake, hybrid source excerpts, technical report, general installer excerpts and Debian workflow. No builds, hardware tests or code changes were performed during this documentation review.
