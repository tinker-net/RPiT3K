# RPi-Ton3K — Native Linux guitar processor

Experimental native Linux port of the TONE3000 × Daisy DIY Pedal. The original Daisy firmware remains separate. The Pi 5 + Pisound deployment is working; the digital processing path has passed the reproducible tests below.

## Architecture

C++20, direct ALSA full duplex, 48 kHz, stereo S32_LE (left input, dual mono output), 64 frames × 3 periods by default. Selectable 64/128/256/512 frames and 2/3/4 periods. Upstream [NeuralAmpModelerCore](https://github.com/sdatkinson/NeuralAmpModelerCore) pinned to `d3189ed482ded880c128bf312941266c4fa5ceec`, float32 sample interface and A2 fast build, with automatic TONE3000 Embedded v2.0.0 dispatch for compatible A2 captures. No JACK, PipeWire or LV2 required.

Signal path: input gain → NAM → optional second NAM → optional cabinet IR → three-band EQ → output gain → finite-value guard and clamp. Full/minimum size selection for compatible slimmable models; fixed-size models subject to Core compatibility. Native FFT partitioned convolution (64-sample partitions), mono WAV IR up to 48,000 samples at 48 kHz, windowed-sinc resampling with sample-rate-ratio gain compensation. No automatic IR loudness normalization or automatic analog NAM calibration. Bypass skips NAM/IR but retains gain and EQ.

Live gain/EQ controls are smoothed. Tuner mode mutes output. SCHED_FIFO priority 60 is requested, with normal-priority fallback; ALSA xrun/suspend recovery restarts both streams. Python web controller, four persistent presets, local NAM/WAV imports, systemd autostart, optional Pisound button and NetworkManager hotspot. Preset switches restart audio and are not gapless. No MIDI control. Experimental TONE3000 account integration is optional and not end-to-end validated. See [Pisound installation and usage](../README-PISOUND.md).

## Automatic hybrid NAM engine — implemented and validated (2026-11-25)

Following a suggestion from the original TONE3000 developer, we implemented an automatic hybrid inference backend in RPi-Ton3K using [TONE3000 Embedded v2.0.0](https://github.com/tone-3000/embedded/tree/v2.0.0) (Cortex-A76 engine) alongside the existing pinned NAM Core. The integration was developed in `embedded-a76`, tested by the maintainer on Raspberry Pi 5 + Pisound, and promoted to `rpi-ui`, `rpi-general` and `deb-packaging`. No upstream pull request was submitted.

- Compatible 48 kHz mono A2-Full (8 channels) and A2-Lite (3 channels) use Embedded automatically, including the selected child of a SlimmableContainer. Selection follows Core's strict less-than breakpoint rule.
- A1 and other Core-supported architectures that do not match the exact A2 signature fall back to NAM Core. Each of the two capture slots selects its backend independently.
- Original .nam files are loaded directly; no .namb conversion or changes to the capture library. Embedded uses 64-frame chunks with continuous state even for larger host buffers. `RPIT3K_NAM_ENGINE=core` forces Core for diagnostic comparisons; `-DRPIT3K_EMBEDDED=OFF` disables Embedded at build time.
- Engine selection is recorded as `NAM_ENGINE=embedded` or `NAM_ENGINE=core` in the controller logs (available at `/api/status`).

### Controlled benchmarks (measured on Pi 5)

Same production executable, same captures and settings, 48 kHz / 64 frames, input gain 1, output gain 0.125, no IR or active effects, service stopped. Three offline runs per backend, alternating order; each run processes 480,000 samples of a 220 Hz sine. Times are per DSP block, excluding ALSA I/O and model loading. Core here is our already optimized A2-fast build, not generic upstream WaveNet.

| Case | Forced Core median (µs) | Auto median (µs) | Speedup | Core worst (µs) | Auto worst (µs) |
| --- | ---: | ---: | ---: | ---: | ---: |
| A2 Full | 147.002 | 55.081 | 2.669× | 190.871 | 110.703 |
| A2 Lite | 36.128 | 13.240 | 2.729× | 56.370 | 41.148 |
| A1 | 273.436 | 273.505 | 1.000× | 318.759 | 374.555 |
| A1 → A2 Full | 423.207 | 337.349 | 1.255× | 571.888 | 444.796 |

Full and Lite reduced median processing time by 62.5% and 63.4%, respectively. The 64-frame deadline is 1,333.33 µs; A2 Full used 4.13% of it on average and Lite 0.99%. These are DSP timing fractions, not total system CPU utilization.

### Numerical equivalence and automatic routing

Four seconds (192,000 float32 samples) of deterministic silence, multitone at several amplitudes, broadband excitation and decay were rendered through the production chain with automatic selection and forced Core. Acceptance: relative RMS residual ≤ −80 dB, maximum absolute sample difference ≤ 1e-4, finite and unclipped output with nonzero reference RMS. Backend logs were asserted for each render. All four buffer sizes (64, 128, 256, 512) produced the same reported metrics for each case.

| Case | Automatic backend | Reference RMS | Residual RMS | Max absolute error | Relative residual | Buffers passed |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| A2 Full | Embedded | 0.024699961 | 4.8871098e-7 | 2.6375055e-6 | −94.07 dB | 4/4 |
| A2 Lite | Embedded | 0.024185072 | 0 | 0 | −∞ dB | 4/4 |
| A1 | Core | 0.019010728 | 0 | 0 | −∞ dB | 4/4 |
| A1 → A2 Full | Core + Embedded | 0.031471144 | 6.0633638e-7 | 2.7269125e-6 | −94.30 dB | 4/4 |

**16/16 null tests passed; HYBRID TEST PASS.** Lite and A1 matched sample-for-sample on this test signal. Full and the mixed chain showed very small numerical differences. This is evidence of equivalence for the tested captures and signal, not proof of bit-identical output for every model.

Test captures (commercial Amalgam files, not redistributed):

- A2: `VX TB30 BR Clean BRI DI.nam`, SHA-256 `20cfcd49680f15d590e183041f549f4d3ce45e915d3d92f76defccfe92dca801`.
- A1: `ORNG GR100 Clean SCP DI.nam`, SHA-256 `589edb83e018337b90d72ff93dc93a7876e2b01021529dae77c978b67f338132`.

### Real-time and regression checks

On Pi 5/Pisound, the native DSP regression suite passed (1/1, 0.30 s), including Hi-Z, FX, gate, convolution and tuner; bypass verification also passed. A live A2 Full preset with two cabinet IRs at 48 kHz / 64 × 3 periods logged 13 consecutive five-second DSP intervals: mean per interval 225.908–263.465 µs, worst observed block 575.056 µs, zero late blocks, zero ALSA recoveries and zero clipped samples. This short live run was not a controlled Core-vs-Embedded comparison.

### Reproduction and scope

From the repository root on a built source installation, substitute your own compatible A2 Full/Lite container and A1 capture paths. Stop the appropriate audio service before timing, then restart it afterwards.

```sh
sudo systemctl stop rpit3k
python3 -u rpi/hybrid_test.py "/path/to/A2.nam" "/path/to/A1.nam"
sudo systemctl start rpit3k
```

The script supports optional `--ir` and `--ir2` for a controlled cabinet-chain comparison; those optional tests have not yet been run. Long-session playing tests, broader capture coverage, other audio interfaces, and new Debian/x86-64 hardware validation remain outstanding. The Pi measurements are shared as reference results across branches, not independent measurements of each deployment. The Pisound source version is the maintainer's stable development baseline; portability and Debian package deployments retain their experimental status.

## Technical validation report — 2026-11-25

### Environment and scope

Raspberry Pi 5 (4 GB), Raspberry Pi OS Lite 64-bit (Debian Trixie), Blokas Pisound. Runtime test uses Amalgam `VX TB30 BR Clean WRM DI.nam` and `WT Blue AC 2x12 121 EQ.wav`. Model SHA256: `3ad426fdd8663e1047f85bb7a65cf1b18eac61c04b5cb9a4ff14e9fd28ee9842`. Architecture SlimmableContainer, native rate 48 kHz, input/output metadata +15/+14 dBu, loudness -10.445415859125216. Commercial assets are not distributed here.

These are operator-reported terminal measurements on target hardware, not CI results or independent laboratory certification. Test sources are included. Latest tested IR script: [f633950](https://github.com/tinker-net/RPiT3K/commit/f6339501d4e7ff1df2080306a01cc676104c92d1).

### Real-time performance

Three consecutive approximately five-second telemetry windows, NAM and IR active, 64 × 3, guitar idle:

| Window | Mean DSP (µs) | Max DSP (µs) | Blocks | Late | Cumulative xruns | Output clip count |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 300.477 | 340.761 | 3751 | 0 | 0 | 0 |
| 2 | 300.767 | 362.723 | 3751 | 0 | 0 | 0 |
| 3 | 301.179 | 353.724 | 3751 | 0 | 0 | 0 |

Period budget 1333.33 µs; mean DSP time 300.81 µs (22.56%); worst observed 362.723 µs (27.20%); worst observed DSP margin 970.61 µs. 11,253 blocks, zero recorded xruns or deadline exceedances. DSP elapsed time includes control polling but excludes ALSA I/O and telemetry; not whole-system CPU utilization or complete callback latency. Logging currently occurs on the audio thread. This short measurement does not establish long-term reliability.

Nominal period 1.333 ms, buffer capacity 4 ms per direction; analog round-trip latency remains unmeasured. Idle input peak 0.00483608 (~-46.31 dBFS), output peak 0.0234389 (~-32.60 dBFS), not played-signal headroom or RMS noise floor. Audible analog interference was reported; its source was not established by telemetry.

### Native DSP and control tests

CTest native_dsp: 1/1 passed (0.18 s). Direct-vs-partitioned convolution checks at lengths 1, 63, 64, 65, 4096, 24000 and 48000; synthetic tuner checks.

`--verify`: PASS in bypass and with NAM + IR.

| Metric | Bypass | NAM + IR |
| --- | ---: | ---: |
| Half output gain | -6.02035 dB | -6.02035 dB |
| Mute RMS | 0 | 0 |
| Zero-input output RMS | 1.4013e-45 | 3.99398e-06 |
| Bass +10 dB at 80 Hz | +9.12079 dB | +9.12049 dB |
| Mid +10 dB at 425 Hz | +10 dB | +9.99991 dB |
| Treble +10 dB at 3 kHz | +8.71871 dB | +8.71871 dB |
| Clipped samples | 0 | 0 |

Shelf response at finite frequencies need not equal the asymptotic setting. Zero-input output residual with this model is about -108 dBFS RMS after test gain, not physical interface noise. These tests cover selected steady-state responses, not every control/transient.

### NAM numerical equivalence

`null_test.py` compares the production Chain (float32 interface, A2 fast define, Cortex-A76 flags) against a separately compiled default upstream Core build (float64 sample interface confirmed by sample_bytes=8; no explicit A2 fast define or A76 flags). Same pinned Core, model and deterministic four-second signal (192,000 samples per run), IR disabled, flat EQ, unity input, output 0.125. No fitted gain or sample alignment.

| Size | Block | Relative RMS residual | Absolute RMS error | Maximum absolute error | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Full | 64 | -97.331 dB | 3.19616173e-7 | 2.04890966e-6 | PASS |
| Full | 128 | -97.331 dB | 3.19616173e-7 | 2.04890966e-6 | PASS |
| Lite | 64 | -97.701 dB | 3.03173619e-7 | 1.91107392e-6 | PASS |
| Lite | 128 | -97.701 dB | 3.03173619e-7 | 1.91107392e-6 | PASS |

Acceptance: relative RMS residual <= -80 dB, maximum absolute error <= 1e-4, equal lengths, finite samples, nontrivial reference and reference peak <0.99. Relative residual = 20 log10(RMS(production-reference)/RMS(reference)). All four runs (768,000 compared samples) passed. Matching aggregate metrics do not prove bitwise block-size invariance. This validates the tested capture against another build of the same upstream Core, not all model architectures, an independent inference implementation or every feature of the official plugin. Full and Lite are each compared to their own reference.

### Independent IR resampling and convolution

`ir_test.py` exercises production WAV loader, resampler and convolution through offline Chain with a synthetic identity NAM. Reference: SciPy resample_poly, Kaiser beta 12, sample-rate-ratio gain compensation. Smooth delayed synthetic impulse, 50 ms.

| Source rate | Expected frames | Relative residual | DC gain deviation | Peak shift | Maximum tail | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 44100 | 2400 | -105.79 dB | -0.0002 dB | 0 | 4.52e-19 | PASS |
| 48000 | 2400 | -100.87 dB | -0.0005 dB | 0 | 1.6e-18 | PASS |
| 96000 | 2400 | -92.59 dB | +0.0008 dB | 0 | 3.2e-18 | PASS |

96-to-48 kHz alias test: equal-amplitude windowed 36 kHz versus 10 kHz tones, -79.88 dB (PASS). Thresholds: residual <= -50 dB, absolute DC deviation <= 0.1 dB, peak shift <= 1 sample, tail <= 1e-5, alias ratio <= -50 dB. Project engineering criteria, not industry certification. These results do not characterize the full transition band or every WAV encoding, IR length or sample rate.

### Updated DSP regression results (2026-11-25)

On Pi 5, the soft-knee expander, convolution and tuner suite passed (1/1, 0.25 s). Bypass --verify also passed with the same gain/EQ/mute measurements above. Maximum convolution error 3.97309e-7 and maximum synthetic tuner error 2.67776 cents. These results do not establish live gate behavior or long-session stability.

### Remaining validation

Long-session stability under realistic load; measured physical ADC–DAC round-trip latency; physical input/output calibration and noise/headroom; additional NAM architectures, dual NAM chains and IRs; physical preset button and network/preset switching robustness. The digital path meets the defined acceptance criteria for tested configurations. Retain the tests as regression checks.

## Build on 64-bit Raspberry Pi OS / Debian

From repository root:

```sh
sudo apt install git build-essential cmake libasound2-dev alsa-utils python3
git clone https://github.com/sdatkinson/NeuralAmpModelerCore.git
git -C NeuralAmpModelerCore checkout d3189ed482ded880c128bf312941266c4fa5ceec
git -C NeuralAmpModelerCore submodule update --init --recursive
cmake -S rpi -B build-rpi -DCMAKE_BUILD_TYPE=Release
cmake --build build-rpi -j2
ctest --test-dir build-rpi --output-on-failure
```

Reuse an existing Core checkout if already present; verify its revision. ARM64 CPU tuning is optional via -DRPIT3K_CPU=cortex-a76 (Pi 5 only); the guided installer selects a target for the detected hardware. Other platforms are not validated.

### Reproduce validation

```sh
cmake --build build-rpi --target nam-reference -j2
./build-rpi/rpit3k --bypass --verify
./build-rpi/rpit3k --model amp.nam --ir cab.wav --verify
python3 rpi/null_test.py amp.nam
sudo apt install python3-numpy python3-scipy
python3 rpi/ir_test.py
./build-rpi/rpit3k --model amp.nam --ir cab.wav --benchmark
```

Substitute real local model/IR paths. Stop live service to avoid resource contention during benchmarks. Offline tests do not require an interface; SciPy and reference executable are test-only dependencies.

## Live audio and web controller

Lower monitor volume and stop competing audio applications before opening ALSA.

```sh
./build-rpi/rpit3k --device hw:pisound --model amp.nam --ir cab.wav --output 0.15
python3 rpi/server.py
```

Run CLI and controller separately, not simultaneously on the same hardware. Controller defaults to loopback with generated credentials. SSH tunnel: `ssh -N -L 8080:127.0.0.1:8080 user@pi-host`, then open http://localhost:8080. Import files, choose preset and Apply. Gain/EQ update live in the active preset; model changes restart audio. Data persists under ~/.local/share/rpit3k.

## Autonomous deployment

```sh
bash rpi/install-service.sh --lan --button
```

Runs as installing user with realtime priority permission and restores last applied preset. The explicit --lan option exposes port 8080 without authentication; default is loopback-only. Trusted isolated LAN only; never expose to Internet. Optional Pisound CLICK_1 cycles presets via loopback API; physical button not yet confirmed. Existing hold/double-click actions retained. CPU metric is total system utilization, displayed buffer duration is nominal, not physical latency.

Optional NetworkManager fallback (requires --lan): `bash rpi/install-hotspot.sh`. WPA2 network at 10.42.0.1 when connectivity absent. Once started it stays active until disconnected or rebooted. Disable with `sudo systemctl disable --now rpit3k-hotspot.timer` and `sudo nmcli connection down RPiT3K-fallback`.

## Portability

The engine and controller accept an ALSA device name via --device, but this branch is the validated Pi-specific baseline. Generic Debian/USB development is separate in [linux-native](https://github.com/tinker-net/RPiT3K/tree/linux-native). No universal interface compatibility is claimed.

## Hi-Z compensation: production DSP validation (2026-11-25)

RPi-Ton3K includes an optional pre-NAM impedance-load compensation filter for passive pickups connected directly to a nominal 100 kΩ input, targeting the response of a nominal 1 MΩ input. It is disabled by default, stored per preset and adjustable live. It does not change physical input impedance. Disable it when using a suitable external buffer or native 1 MΩ instrument input.

The circuit approximation uses a series pickup resistance and inductance, a shunt capacitance of 470 pF, and the volume-pot resistance. With load conductance G = 1/Rload + 1/Rvolume, the transfer function is H(s) = 1/[1 + (R + sL)(G + sC)]. The correction is H(1 MΩ)/H(100 kΩ), discretized as a biquad using the bilinear transform at 48 kHz. Partial compensation is a linear blend of the dry and corrected signals, not a percentage of physical impedance.

### Reproducible test

From the repository root, with the current engine already built:

```sh
python3 rpi/hiz_test.py build-rpi/rpit3k
```

The test requires only Python's standard library. It renders synthetic sine waves through the actual production DSP executable in offline bypass mode (NAM and cabinet convolution bypassed; compensation remains active). Four profiles × eight frequencies × three settings (0%, 80%, 100%) = 96 renders. The script compares the measured complex frequency response (amplitude and phase) with an independently evaluated lumped-element circuit using the bilinear frequency mapping. The acceptance threshold is an absolute complex transfer-function error of 1e-4. It also reports the RMS difference between enabled and disabled output.

Measured on the maintainer's Raspberry Pi 5, all four profiles passed:

| Profile | Maximum complex error | Result |
|---|---:|---|
| Telecaster | 2.13e-5 | PASS |
| Stratocaster | 1.97e-5 | PASS |
| PAF | 2.69e-5 | PASS |
| P90 | 3.43e-5 | PASS |

Measured gain relative to compensation OFF, at 80% (dB):

| Frequency | Telecaster | Stratocaster | PAF | P90 |
|---|---:|---:|---:|---:|
| 82 Hz | 0.47 | 0.36 | 0.48 | 0.51 |
| 440 Hz | 0.52 | 0.38 | 0.54 | 0.60 |
| 1 kHz | 0.75 | 0.50 | 0.87 | 1.07 |
| 2 kHz | 1.88 | 1.04 | 2.62 | 3.67 |
| 3 kHz | 4.60 | 2.45 | 7.61 | 9.22 |
| 4 kHz | 6.76 | 5.43 | 7.10 | 5.70 |
| 5 kHz | 4.42 | 6.28 | 3.42 | 2.87 |
| 8 kHz | 1.05 | 1.29 | 0.78 | 0.73 |

For example, the Telecaster profile at 4 kHz measured +7.86 dB at 100%, +6.76 dB at 80%, and a nonzero enabled-vs-disabled residual RMS of 0.0065481 at 100%. This confirms that the production executable actually applies the intended frequency-dependent correction. The 80% setting is a provisional conservative starting point for the maintainer's Telecaster with Tex-Mex pickups, not a measured optimum.

**Validation scope:** this is a digital, model-relative test, not a physical measurement of the guitar, Pisound ADC, or an actual 1 MΩ input. Pickup inductance, capacitance and pot values are illustrative assumptions; cable and pickup variations may change the real response. The test does not validate live-control delivery, real-time CPU overhead, noise recovery or electrical equivalence. The general Linux branch shares the filter implementation but these results are inherited from the Pi test, not a new x86/USB measurement. A controlled comparison with a physical high-impedance buffer or selectable input load remains future work. Allow headroom for resonance boosts (over 10 dB in some profiles).



Native effects use DaisySP-LGPL. See [source and license information](vendor/daisysp/README.md).
