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
| linux-native | 45de75bf79c4037e631f62da7d9124d6a2b2c5e3 | Earlier generic Linux ALSA prototype |
| rpi-native | 096ba12408654bd7d01335018f12326dd2bbc685 | Original native ALSA/DSP prototype |

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
- Recent UI requests: start with audio off; improve tuner and use tuning-fork icon; order tuner, explicit audio on/off and input calibration before power menu (shutdown/reboot). Implemented in all three deployment branches according to commit history and server source: --autostart ignored, tuner pitch in fast telemetry, opt-in poweroff/reboot endpoints. Physical/UI operation not freshly tested.
- Historical UI tags mentioned: ui-classic-original and ui-tone3000-v1; verify refs before using them.

## Primary references

- [Stable technical report and reproducible tests](../rpi/README.md)
- [Build configuration](../rpi/CMakeLists.txt)
- [Hybrid dispatch](../rpi/hybrid_nam.h)
- [Hybrid test harness](../rpi/hybrid_test.py)
- [General installer](https://github.com/tinker-net/RPiT3K/blob/f468bd64d17c5656e5c199da79bf4f6b442c7747/rpi/install-general.sh)
- [Debian CI workflow](https://github.com/tinker-net/RPiT3K/blob/cbffb7dc10a7bd0a21783f4b49854426fb6ede1e/.github/workflows/deb-packaging.yml)

This review verified repository metadata, branch refs, CMake, hybrid source excerpts, technical report, general installer excerpts and Debian workflow. No builds, hardware tests or code changes were performed during this documentation review.

## Historical commit review — 2026-11-26

Reviewed commit subjects across all seven branches, paging through native development history, and sampled current controller, build/install scripts and UI. This is an architectural review, not a line-by-line audit of every patch.

| Milestone | Representative commits (rpi-ui unless noted) |
|---|---|
| Native ALSA, duplex recovery and bypass | fa3dbb7d, 29eacd7b, 3d1d529f, f9f6b987 |
| Controller, four presets, browser UI, FFT IR, tuner | 9183475d, abc1fdd3, 3eea9de9, 6676c334 |
| Live controls and numerical reference | f889e9af, 977f999f, d73beff8, 18a3e227, f6339501, dea94c10 |
| Generic Linux predecessor | linux-native: 6b750a1a, ec67bab8, d7fce887, d7fa7da0, 45de75bf |
| Telemetry and cloud | b44cee69, 4497a317, 9e0042a4, b6657c72, 0b4bf527 |
| Gate evolution | bd9b8639, 775e51da, 943533bf, 888dbca2, 11ab55f6 |
| FX and explicit calibration | b93151cc, f9165cd4, 47200594, aa3b1287, 773d9cb3 |
| Library and UI | fb3e9bd7, 28bc269b, fc0a40ed, 5f982088, f28afaf9 |
| Dual IR and Hi-Z | fbeee090, 42e3bdc4, aa3d8c5e, 5c88a94e, 1ebd1ea3, 4f6547de |
| General edition | rpi-general: af1f876c, 4a591528, d697b4e6, c7a19294, 0b989ae1 |
| Packaging | deb-packaging: 1d66553d, e892dd29, de22fab7, fe0df44e |
| Hybrid | embedded-a76: 26b65fd5, 14b27ea4, d95599e4; rpi-ui: 99f19910, 39c189a3 |
| Classic/T3K skin | 4d42c383, dbdc2065, c774ebd4, e2cb03c4 |
| Companion withdrawn | a6fd1a27, f7771170, 07650025, e6029489 |
| Latest controls | 4c68b72b, e18170e3, d1c2e3ea, 8bee8135, 654dfd68; general f468bd64; packaging cbffb7dc |

Preserve intentional behavior: soft-knee continuous downward expander (not binary gate), input-keyed downstream noise suppression, 120 ms hold/350 ms release history; optional pre/post compression, FDN reverb with tail draining and unused processing skipped; live smoothed controls; 64-frame IR partitions independent of ALSA periods, parallel dual IR linear blend; per-preset optional Hi-Z A/B and explicit ADC reference (invalidate on generic routing change); real nested library folders, favorites and preset reference migration on rename/move, confirmed permanent deletion rather than trash; custom WebP artwork and SVG fallback; selectable Classic/T3K skin; cloud off by default and separate from withdrawn Companion; confirmed opt-in host power actions. Preserve device/channel routing differences and separate data/service paths across editions.

### Newly identified consistency risk (not fixed)

All three current server.py files explicitly ignore --autostart and start audio stopped. The rpi-ui install-service.sh and rpi-general install-general.sh still pass --autostart and retain a live-audio telemetry readiness check. A clean install may report failure despite the service starting correctly in its intended silent state. Confirm actual installer behavior before fixing; do not restore automatic audio start. Reboot endpoint/UI existence does not prove sudo permissions are installed on every host.

### x86 follow-up evidence

Current general installer and packaging/build-deb.sh invoke CMake without disabling RPIT3K_EMBEDDED. Thus the default A76 source selection is requested on AMD64 too; this does not establish the compiled implementation or actual runtime routing. CI run retrieval attempted but rejected by connector; no successful run claimed. Inspect upstream engine source and actual build logs before proposing architecture changes.

No new builds or hardware tests; only documentation updated.

## Live rig experiment — 2026-11-26

User requirements: retain the complete York Audio IR within the supported duration; optimize convolution without truncation, lowering the sample rate, or adding callback delay; apply all rig changes automatically, keep Audio ON/OFF exclusively for audio power, and clarify ADC calibration. Preserve silent boot and the stable deployment branches.

Experimental branch: [live-rig](https://github.com/tinker-net/RPiT3K/tree/live-rig), forked from rpi-ui at 7034920a35720163bd0106ef61fe17aa0df0a1e9. No promotion to rpi-ui, rpi-general or deb-packaging yet.

- f74463f: packed, padded split real/imaginary FFT spectra and precomputed permutation; all original taps retained; 64-frame partitions, 128-point FFT, 48000-sample maximum at 48 kHz; oversize IRs rejected, never silently shortened. Pinned NAM WAV decoder reads entire valid mono PCM/float WAV; non-48 kHz IRs resampled at full duration.
- 797f294 / 4ce2c57 / 293449e / f92a8a9: worker builds new rig off the audio thread; atomic pointer exchange, 64-sample fade out and fade in, old rig destroyed by worker, independent acknowledgement channel. No ALSA reopen for NAM/IR/quality/bypass/preset/tuner switching while running; not gapless in the strict sense, tails and model state reset on structural swaps. Hardware buffer/period settings still reopen ALSA.
- e9cf868 / 9772368: acknowledged controller switching, automatic browser edits and persistent presets including when audio is off; no implicit audio start. Explicit ON/OFF retained. Hardware changes apply automatically; reference-only changes do not reopen ALSA.
- 81f52b8: display ADC and capture references, target correction and current input gain; calibration remains deliberate, not forced on every capture. +1.14 dBu is nominal, derived from Blokas 2.5 Vpp at minimum gain, not a physical measurement. Formula ADC dBu minus NAM input_level_dbu, convert to linear amplitude; current implementation calibrates first NAM only. No inter-model output calibration; missing metadata cannot be corrected. See https://www.tone3000.com/guides/nam-calibration and https://blokas.io/pisound/docs/audio/.
- 219f270 / a671c02: synthetic worker regression and CTest registration.
- f0984df: isolated experimental ARM64 and AMD64 build workflow, results not yet verified.

Actual local isolated tests on x86_64, GCC 14.2, -O3: convolution tested with 1, 63, 64, 65, 2048, 9600, 24000 and 48000 taps; impulse reconstruction including last sample and initial 512-frame direct reference, max errors 5.22e-8 and 6.46e-8 respectively. New packed accumulation faster in preliminary isolated timing for long IRs; no controlled Pi comparison yet. LiveRigLoader mock: 20 successful exchanges, old-object destruction off audio thread, invalid rig rejected with current object unchanged. Local git blob hashes matched published convolution.h, live_rig.h and live_rig_test.cpp. These tests do not validate the complete engine, real NAM loads, browser/server integration, actual ALSA streams, concurrent inference/loading, switching under CPU load, or audible transitions. Full build, existing numerical regression, real Pisound test, comparison of DSP timing/xruns with long York IRs and migration across deployment branches remain required before promotion.

Known prior installer readiness inconsistency remains out of scope. No code was changed on stable branches.

## Branch maintenance policy — 2026-11-26

User explicitly requests maintaining rpi-ui (Pisound) and rpi-general (generic ALSA) at the latest feature level, without creating branches for each change. Port shared changes to both in the same task, preserving hardware routing, service/data paths and edition-specific defaults. Do not create new branches unless explicitly requested. The existing live-rig experiment is retained as historical reference; do not use it for ongoing development. The live-rig changes are promoted at the user's request; full builds and real hardware validation remain outstanding. deb-packaging is unchanged by this promotion. No claim of fresh test results.
