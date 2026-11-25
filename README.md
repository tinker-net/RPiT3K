# RPi-Ton3K General — Native NAM guitar processor for Linux

## Download experimental Debian packages

[**Download packages from GitHub Actions**](https://github.com/tinker-net/RPiT3K/actions/workflows/deb-packaging.yml?query=branch%3Adeb-packaging)

Open the latest successful run and download the matching artifact (GitHub sign-in may be required). Extract the ZIP before installing.

| Artifact | Target |
|---|---|
| rpi-ton3k-pi5 | Raspberry Pi 5 / Cortex-A76 |
| rpi-ton3k-pi4 | Raspberry Pi 4 / Cortex-A72 |
| rpi-ton3k-arm64 | Generic ARM64 |
| rpi-ton3k-amd64 | x86-64 |

On a clean Debian 13 / Raspberry Pi OS Trixie 64-bit system, from the extracted package directory:

```sh
sudo apt install ./*.deb
```

Install only one matching package. The service listens on localhost:8080 by default. For remote access use SSH forwarding: `ssh -L 8080:127.0.0.1:8080 user@raspberrypi`, then open http://localhost:8080. Configure audio in the browser. Pisound drivers must already be installed. See [package installation and migration notes](packaging/README.md).

The first CI run was reported successful by the maintainer. Physical audio and systemd operation on real hardware remain unverified. These are experimental packages, not a stable release. Existing source installations must be stopped and disabled before installing; their data is not automatically migrated. Actions artifacts are temporary; persistent release assets are not yet published.

**Experimental portability branch · Linux ARM64 / x86-64 · ALSA · MIT**

This branch is derived from the current `rpi-ui` Pisound edition. It retains all DSP, presets, browser controls and experimental cloud functionality, but replaces fixed Pisound routing with configurable ALSA PCM and channel mapping. All measurements below are inherited from Pi 5/Pisound, not new USB or x86-64 results.

RPiT3K is an independent open-source guitar processor inspired by the [TONE3000 × Daisy DIY Pedal](https://github.com/tone-3000/t3k-diy-pedal). It turns a Raspberry Pi equipped with [Blokas Pisound](https://blokas.io/pisound/) into a standalone neural amplifier and cabinet processor, controlled from a browser.

The goal is a small, reproducible, offline-capable guitar rig rather than a general-purpose plugin host: native NAM inference, a predictable audio path, low buffering, persistent presets and transparent engineering measurements. The Raspberry Pi implementation does not run the Daisy firmware or its embedded inference engine.

**[General installation guide](README-GENERAL.md)** · **[Pisound edition](https://github.com/tinker-net/RPiT3K/tree/rpi-ui)** · **[Technical report and test reproduction](rpi/README.md)** · **[Original Daisy documentation](README-DAISY.md)**

## Web interface

![RPiT3K running on Raspberry Pi and Pisound, with local capture library, amplifier view, rig controls, live meters and collapsible effects](docs/images/rpit3k-interface.png)

*Actual RPiT3K interface running on the development hardware. The screenshot illustrates a live preset with NAM and cabinet IR selected; it is not a mockup.*

## Results at a glance

| Measurement | Observed result | Scope |
| --- | ---: | --- |
| Mean DSP processing time | 300.81 µs / 22.56% of period | Earlier Pi 5 build, one NAM + IR |
| Worst observed DSP time | 362.723 µs / 27.20% of period | Same short measurement |
| ALSA recovery events / late DSP blocks | 0 / 0 | 11,253 blocks, approximately 15 s |
| NAM relative RMS null residual | −97.33 to −97.70 dB | Full and Lite versus default upstream Core |
| IR convolution maximum absolute error | 3.97309 × 10⁻⁷ | Latest native DSP test, up to 48,000 taps |
| IR resampling relative residual | −92.59 to −105.79 dB | Three source sample rates |
| Latest native DSP regression suite | PASS (1/1, 0.25 s) | Expander, convolution, tuner |
| Latest bypass verification | PASS | Gain, EQ, mute and clipping |

These are developer-reported results obtained on actual Raspberry Pi hardware, not independent certification or CI results. The performance and NAM/IR comparison measurements precede the latest meter and expander additions. No new integrated real-time benchmark is claimed for the current revision.

## Features

- Native mono NAM captures using pinned NeuralAmpModelerCore, including compatible A2 slimmable Full and Lite models.
- Optional second NAM and independent cabinet IR. No conversion to Daisy .namb format.
- Mono WAV IR up to one second at 48 kHz, partitioned FFT convolution and windowed-sinc sample-rate conversion.
- Live input/output gains, three-band EQ and soft-knee input-keyed noise reduction.
- Chromatic tuner with muted output; input/output digital peak meters, CPU, temperature, nominal ALSA buffer and recovery counter.
- Four persistent presets, nested local file library, responsive browser interface and offline playback.
- systemd startup, optional physical Pisound button preset cycling and fallback NetworkManager hotspot.
- Experimental TONE3000 account browsing/import, disabled by default in new service installations pending verification and API compliance.

## Architecture

```text
Pisound ADC (left channel)
    ├── Input peak meter
    ├── Noise-reduction detector ────────────────────────────────┐
    └── Input gain → NAM 1 → optional NAM 2 → optional IR → EQ   │
                                             → Output gain → attenuation
                                             → finite guard / clamp
                                             → output peak meter
                                             → Pisound DAC (dual mono)

Browser → Python HTTP controller → native C++ engine
                 ├── local presets and model library
                 ├── live controls (private stdin pipe)
                 ├── level telemetry (nonblocking pipe)
                 └── optional cloud client (outside audio engine)
```

The native C++20 engine uses ALSA directly at 48 kHz with stereo S32_LE interleaving, left-channel input and dual-mono output. No JACK, PipeWire or LV2 host is required. The controller requests SCHED_FIFO priority 60 with normal-priority fallback. ALSA underrun/overrun or suspend recovery restarts both streams. Model and preset changes currently restart audio; switching is not gapless.

The inference backend is [NeuralAmpModelerCore](https://github.com/sdatkinson/NeuralAmpModelerCore) at commit `d3189ed482ded880c128bf312941266c4fa5ceec`, built with float32 sample interface and A2 fast-path enabled. The original project's three-band EQ is reused. Cabinet convolution, WAV resampling, tuner, expander, ALSA and web control are native implementation components. The browser is not in the real-time audio path.

| Control | Range / behavior |
| --- | --- |
| Input | 0–2× linear gain |
| Bass / Mid / Treble | ±20 / ±15 / ±10 dB |
| Output | 0–1× linear gain |
| Gate | OFF or −80 to −30 dBFS |
| Buffer | 64, 128, 256, 512 frames; 2–4 periods |
| Bypass | Skips NAM/IR, retains gain, EQ and enabled expander |

### Noise reduction

The latest implementation is a downward expander, not an all-or-nothing gate. It detects the raw input and attenuates the processed output, including residual model noise. The curve uses a 6 dB soft knee, 4:1 downward expansion, up to 90 dB attenuation, approximately 30 ms peak-envelope decay, 1 ms gain opening and 350 ms gain closing time constants. No lookahead. The target is recalculated every 16 samples; gain is smoothed sample by sample. OFF bypasses the expander.

For a constant −45 dBFS detector level, theoretical steady-state gain is −2.25 dB at threshold −45 and −4 dB at threshold −44: a difference of 1.75 dB, rather than a binary mute. The automated test checks this transition as well as opening, release, deep attenuation and OFF transparency. Musical sustain and noise suppression with real pickups still need listening tests. Noise generated after the DAC cannot be removed digitally.

## Experimental effects and calibration

The latest revision adds an Amount-controlled compressor with selectable PRE/POST NAM position and a mono four-line feedback delay network reverb with Spring-style, Plate-style and Room voicings, Mix and Decay (0.2–5 s). These are algorithmic voicings, not physical spring/plate models or measured IRs. Both effects default to OFF in existing presets and are adjustable live. The reverb follows noise reduction so the expander does not cut its tail. Final output gain follows both effects. Calibrate Input reads NAM input_level_dbu metadata and computes 10^((ADC reference − model reference)/20); the suggested +1.14 dBu Pisound reference is nominal at minimum gain, not measured. Missing metadata or out-of-range compensation is rejected. The Pi 5 native FX regression tests now pass (see below). Historical NAM + IR real-time measurements still do not cover active FX.

## Technical validation

### 1. Test platform and real-time performance

Raspberry Pi 5, 4 GB RAM, Raspberry Pi OS Lite 64-bit (Debian Trixie), Blokas Pisound, 48 kHz, 64 frames × 3 periods. Earlier benchmark used a commercial 48 kHz slimmable NAM capture and mono cabinet IR (identifiers and model hash in the [technical report](rpi/README.md)); neither asset is distributed.

Three consecutive telemetry windows, guitar idle:

| Window | Mean DSP (µs) | Maximum (µs) | Blocks | Late | Cumulative recoveries | Clipped samples |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 300.477 | 340.761 | 3751 | 0 | 0 | 0 |
| 2 | 300.767 | 362.723 | 3751 | 0 | 0 | 0 |
| 3 | 301.179 | 353.724 | 3751 | 0 | 0 | 0 |

At 48 kHz a 64-frame period lasts 1.333 ms. The mean measured DSP cost is 22.56% of that budget; the worst observed cost is 27.20%, leaving 970.61 µs before the DSP deadline in that window. This is **not whole-system CPU utilization**: timing includes control polling and chain processing but excludes ALSA I/O and telemetry. No controlled comparison against PiPedal, TONEX or other processors has been performed.

Nominal buffer capacity is 4 ms per direction (64 × 3 / 48,000), not measured round-trip latency. Analog ADC-to-DAC latency requires a physical loopback measurement. Zero recoveries in 15 seconds does not establish long-term reliability or dual-NAM performance.

### 2. NAM numerical fidelity

The production engine was compared against a separately built upstream default Core (double sample interface, no explicit A2 fast define or Cortex-A76 flags). Same Core revision and capture; 192,000 deterministic samples per run, flat EQ, unity input, output gain 0.125, no IR. No fitted gain or alignment.

| Model | Block | Relative RMS residual | Absolute RMS error | Maximum absolute error |
| --- | ---: | ---: | ---: | ---: |
| Full | 64 | −97.331 dB | 3.19616173e-7 | 2.04890966e-6 |
| Full | 128 | −97.331 dB | 3.19616173e-7 | 2.04890966e-6 |
| Lite | 64 | −97.701 dB | 3.03173619e-7 | 1.91107392e-6 |
| Lite | 128 | −97.701 dB | 3.03173619e-7 | 1.91107392e-6 |

All four runs passed the defined criteria (relative RMS residual ≤ −80 dB, maximum absolute error ≤ 1e-4, finite equal-length outputs and nontrivial unclipped reference). This represents 768,000 compared samples. Relative residual is 20 log10(RMS(production − reference) / RMS(reference)). It is not an absolute noise-floor measurement.

The results support numerical agreement with the upstream inference path for the tested model. Full and Lite are each compared against their own reference, not against one another. Equal aggregate error at two block sizes is not proof of bitwise invariance. This does not independently validate the underlying neural network or establish equivalence to every official plugin feature.

### 3. Cabinet IR fidelity

The latest native test compares partitioned convolution against direct convolution:

| IR length (samples) | Maximum absolute error |
| ---: | ---: |
| 1 | 4.71026e-9 |
| 63 | 1.28446e-7 |
| 64 | 1.08471e-7 |
| 65 | 1.07153e-7 |
| 4096 | 3.17334e-7 |
| 24000 | 3.93376e-7 |
| 48000 | 3.97309e-7 |

All pass the 1e-4 absolute-error threshold. The largest observed error corresponds to approximately −128 dB relative to unit amplitude, not measured analog noise or a listening-test result.

An earlier independent test exercised the actual WAV loader, resampler and production chain with a synthetic identity NAM and compared to SciPy resample_poly (Kaiser beta 12, sample-rate-ratio gain compensation):

| Source rate | Output samples | Relative residual | DC deviation | Peak shift | Max tail |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 44.1 kHz | 2400 | −105.79 dB | −0.0002 dB | 0 | 4.52e-19 |
| 48 kHz | 2400 | −100.87 dB | −0.0005 dB | 0 | 1.6e-18 |
| 96 kHz | 2400 | −92.59 dB | +0.0008 dB | 0 | 3.2e-18 |

96→48 kHz alias rejection, 36 kHz versus 10 kHz equal-amplitude windowed tones: −79.88 dB. All pass the project criteria. These tests demonstrate timing and gain preservation for selected synthetic signals, not the complete frequency response or every WAV encoding. No automatic IR loudness normalization is applied.

### 4. Gain, EQ and digital silence

| Metric | Latest bypass | Earlier NAM + IR |
| --- | ---: | ---: |
| Half output gain | −6.02035 dB | −6.02035 dB |
| Mute RMS | 0 | 0 |
| Zero-input RMS | 1.4013e-45 | 3.99398e-6 |
| Bass +10 dB at 80 Hz | +9.12079 dB | +9.12049 dB |
| Mid +10 dB at 425 Hz | +10 dB | +9.99991 dB |
| Treble +10 dB at 3 kHz | +8.71871 dB | +8.71871 dB |
| Clipped samples | 0 | 0 |

Both verification runs passed. Finite-frequency shelf gains need not equal their asymptotic gain. The modeled zero-input residual is approximately −108 dBFS RMS after test gain; it is not the Pisound analog noise floor.

Earlier idle telemetry showed maximum raw input peak 0.00483608 (−46.31 dBFS) and processed output peak 0.0234389 (−32.60 dBFS). These are peaks, not RMS noise measurements. They do not identify the cause of analog interference. A metadata-based Calibrate Input action is now available using an explicitly entered ADC full-scale reference in dBu. It is not an automatic physical measurement; calibrated hand-off between captures is not implemented. A physical voltage calibration is needed before claiming calibrated analog response.

### 5. Tuner and current regression status

| Test frequency (Hz) | Detected (Hz) | Error (cents) |
| ---: | ---: | ---: |
| 41.2034 | 41.2039 | 0.0223 |
| 82.4069 | 82.4135 | 0.1385 |
| 110 | 110.006 | 0.1011 |
| 146.832 | 146.868 | 0.4230 |
| 196 | 196.048 | 0.4210 |
| 246.942 | 247.127 | 1.2939 |
| 329.628 | 330.138 | 2.6778 |
| 440 | 440.39 | 1.5323 |

All synthetic tuner tests pass the 5-cent limit. The latest Pi 5 test output reports `Soft-knee expander PASS`, `100% tests passed, 0 tests failed out of 1`, total time 0.25 s, and separate `VERIFY PASS` in bypass. This confirms the implemented regression checks, not full hardware or subjective sound quality.

### 6. Native effects regression and isolated performance

On Raspberry Pi 5, the expanded native DSP suite reported `Native FX PASS`, `Soft-knee expander PASS`, 1/1 tests passed in 0.27 s. Bypass `--verify` passed with the same reported gain, EQ and mute results as before. The new unit tests cover compressor attenuation, three FDN reverb impulse decays and return to bypass.

Offline benchmark with the service stopped, 48 kHz, 64-frame blocks, NAM and IR bypassed:

| Configuration | Mean DSP (µs) | Maximum DSP (µs) | Mean share of 1333.33 µs period |
| --- | ---: | ---: | ---: |
| Baseline | 1.89861 | 14.815 | 0.142% |
| Compressor 0.5, PRE | 2.16995 | 48.834 | 0.163% |
| Reverb mix 0.3, decay 2 s, default voice | 5.52232 | 49.445 | 0.414% |
| Compressor + reverb + gate −45 dBFS | 5.10517 | 20.463 | 0.383% |

Observed mean incremental cost of the combined configuration relative to baseline: 3.20656 µs (0.240% of period). These are single offline runs on a synthetic input, not end-to-end real-time timings. The combined result being lower than the reverb-only result does not imply that additional effects improve performance; run-to-run variability was not characterized. No conclusion about xruns, active NAM + IR performance, physical calibration, or subjective sound quality follows from this benchmark.

Reproduce with the live service stopped:

```bash
./build-rpi/rpit3k --bypass --benchmark
./build-rpi/rpit3k --bypass --comp 0.5 --benchmark
./build-rpi/rpit3k --bypass --reverb 0.3 --decay 2 --benchmark
./build-rpi/rpit3k --bypass --comp 0.5 --reverb 0.3 --decay 2 --gate -45 --benchmark
```

## Installation

See [README-GENERAL.md](README-GENERAL.md) for generic Linux installation and routing. The guided installer targets 64-bit Debian-family Linux on ARM64 or x86-64; other distributions require a manual build. No Blokas software is installed automatically.

```bash
sudo apt update
sudo apt install -y git
git clone --branch rpi-general https://github.com/tinker-net/RPiT3K.git RPiT3K-General
cd RPiT3K-General
bash rpi/install-general.sh
```

Default device is ALSA `default`, 256 frames × 3 periods, two capture and playback channels. The web interface permits explicit PCM and channel mapping. Compatibility is not universal: driver, supported formats, channel counts, clock, period constraints and host performance determine operation. No physical USB or x86-64 test has yet been performed.

## Reproduce the engineering checks

```bash
ctest --test-dir build-rpi -V
./build-rpi/rpit3k --bypass --verify
./build-rpi/rpit3k --model amp.nam --ir cab.wav --verify
cmake --build build-rpi --target nam-reference -j2
python3 rpi/null_test.py amp.nam
sudo apt install python3-numpy python3-scipy
python3 rpi/ir_test.py
./build-rpi/rpit3k --model amp.nam --ir cab.wav --benchmark
```

Replace example paths with compatible local assets. Stop the live service before benchmarking to avoid contention. Offline tests do not require audio hardware. See the detailed report for exact reference settings and acceptance criteria.

## Project status and contributions

RPiT3K is a preview suitable for community testing, not a certified stage-ready product. The remaining work includes clean installation and reboot tests, extended playing sessions with the current build, latency loopback and analog calibration, Pi 4 validation, dual-NAM and additional architecture benchmarks, physical preset-button verification, hotspot robustness, and end-to-end cloud authentication/download testing.

Useful bug reports include Pi model, OS version, commit, ALSA settings, model architecture, DSP timing, recovery count and reproducible steps. Do not attach private credentials or copyrighted captures. The original Pisound edition remains on `rpi-ui`; this branch is the current general Linux development version.

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

## Credits and license

The original TONE3000 × Daisy DIY Pedal and reused EQ are licensed under MIT (see [LICENSE](LICENSE)). Thanks to TONE3000, the NeuralAmpModelerCore contributors, Blokas and the open-source audio community. RPiT3K is an independent fork, not an official product or an endorsed integration. Original firmware and hardware documentation remain in [README-DAISY.md](README-DAISY.md). Dependencies retain their respective licenses; model and IR rights remain with their authors.
