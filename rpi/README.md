# RPiT3K — Native Linux guitar processor

Experimental native Linux port of the TONE3000 × Daisy DIY Pedal. The original Daisy firmware remains separate. The Pi 5 + Pisound deployment is working; the digital processing path has passed the reproducible tests below.

## Architecture

C++20, direct ALSA full duplex, 48 kHz, stereo S32_LE (left input, dual mono output), 64 frames × 3 periods by default. Selectable 64/128/256/512 frames and 2/3/4 periods. Upstream [NeuralAmpModelerCore](https://github.com/sdatkinson/NeuralAmpModelerCore) pinned to `d3189ed482ded880c128bf312941266c4fa5ceec`, float32 sample interface and A2 fast build. No JACK, PipeWire or LV2 required.

Signal path: input gain → NAM → optional second NAM → optional cabinet IR → three-band EQ → output gain → finite-value guard and clamp. Full/minimum size selection for compatible slimmable models; fixed-size models subject to Core compatibility. Native FFT partitioned convolution (64-sample partitions), mono WAV IR up to 48,000 samples at 48 kHz, windowed-sinc resampling with sample-rate-ratio gain compensation. No automatic IR loudness normalization or automatic analog NAM calibration. Bypass skips NAM/IR but retains gain and EQ.

Live gain/EQ controls are smoothed. Tuner mode mutes output. SCHED_FIFO priority 60 is requested, with normal-priority fallback; ALSA xrun/suspend recovery restarts both streams. Python web controller, four persistent presets, local NAM/WAV imports, systemd autostart, optional Pisound button and NetworkManager hotspot. Preset switches restart audio and are not gapless. No MIDI or TONE3000 account integration yet.

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

Reuse an existing Core checkout if already present; verify its revision. Current ARM64 build targets Cortex-A76. Other platforms are not validated.

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
bash rpi/install-service.sh
```

Runs as installing user with realtime priority permission, restores last applied preset, exposes port 8080 without authentication. Trusted isolated LAN only; never expose to Internet. Optional Pisound CLICK_1 cycles presets via loopback API; physical button not yet confirmed. Existing hold/double-click actions retained. CPU metric is total system utilization, displayed buffer duration is nominal, not physical latency.

Optional NetworkManager fallback: `bash rpi/install-hotspot.sh`. WPA2 network at 10.42.0.1 when connectivity absent. Once started it stays active until disconnected or rebooted. Disable with `sudo systemctl disable --now rpit3k-hotspot.timer` and `sudo nmcli connection down RPiT3K-fallback`.

## Portability

The engine and controller accept an ALSA device name via --device, but this branch is the validated Pi-specific baseline. Generic Debian/USB development is separate in [linux-native](https://github.com/tinker-net/RPiT3K/tree/linux-native). No universal interface compatibility is claimed.
