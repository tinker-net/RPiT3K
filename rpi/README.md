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

Reuse an existing Core checkout if already present; verify its revision. On this branch the default build is architecture-generic. On ARM64, optionally pass `-DRPIT3K_CPU=cortex-a76` for a Pi 5 or an appropriate compiler-supported CPU target for other hardware. The measurements above were obtained on the Pi-specific baseline, not this branch.

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

## Generic Debian / USB audio quick start

This branch is experimental. The validation report above is inherited from the Raspberry Pi baseline; generic Linux builds and physical USB audio have not yet been validated. The production DSP algorithms are unchanged.

On Debian with ALSA, a C++20 compiler, CMake and Python 3, follow the build instructions above. Discover the interface:

```sh
arecord -l
aplay -l
```

Choose the same full-duplex interface for capture and playback, using the ALSA card identifier rather than its numeric index when possible. Replace USB below with the actual identifier and select the logical input channel (1 or 2). On interfaces such as the Scarlett Solo, the instrument jack may correspond to channel 2.

```sh
./build-rpi/rpit3k --device plughw:CARD=USB,DEV=0 --input-channel 2 \
  --buffer 256 --periods 3 --bypass --output 0.1
```

Lower monitor/headphone volume first, disable hardware direct monitoring to avoid hearing a parallel unprocessed signal, and stop other programs that occupy the interface. Use the instrument/Hi-Z input for passive guitar pickups. Ctrl+C stops the engine. The ALSA engine requests 48 kHz, stereo S32_LE and matching capture/playback period and buffer sizes. It logs the actual sizes and rejects mismatches rather than silently changing timing. Try 128, 256 or 512 frames and 2–4 periods if 64 frames is unsupported. `hw:` is direct hardware access; `plughw:` explicitly permits ALSA format/channel/rate adaptation and may introduce extra latency. No guarantee that every interface or channel layout is supported. Interfaces with more than two hardware channels may require a custom ALSA route PCM. Separate unsynchronized input/output devices are not supported as a reliable configuration. USB hotplug recovery is not implemented.

For the web controller:

```sh
python3 rpi/server.py --device plughw:CARD=USB,DEV=0 --input-channel 2 \
  --data ~/.local/share/rpit3k-linux
```

Open http://127.0.0.1:8080 and use the credentials printed in the terminal. Import models/IRs, select a preset and Apply. Start with a conservative buffer in the settings. Stop the CLI before starting the controller. If using a remote machine, forward port 8080 over SSH. Do not expose unauthenticated HTTP to the network.

## Generic systemd deployment

Run as the normal audio user after a successful manual trial:

```sh
bash rpi/install-service.sh plughw:CARD=USB,DEV=0 2
sudo journalctl -u rpit3k-linux -f
```

The separate `rpit3k-linux.service` grants realtime-priority permission, binds the unauthenticated controller only to loopback, and uses ~/.local/share/rpit3k-linux. It does not install Pisound button support or modify the original Pi service. Do not run both services concurrently (shared port and possibly shared hardware). On a fresh checkout the initial preset may be bypass; import and apply a NAM/IR to test actual processing.

```sh
sudo systemctl disable --now rpit3k-linux
```

Use the offline regression checks above on each target, then run the actual NAM + IR preset and check DSP telemetry for late blocks, xruns and clipping. DSP timing excludes ALSA I/O; latency must be measured physically. For reliable operation over long sessions, verify the chosen interface and buffer configuration under realistic load. The generic branch does not claim universal Debian or USB compatibility.

The Pi-specific deployment, Pisound integration and original technical baseline remain in [rpi-native](https://github.com/tinker-net/RPiT3K/tree/rpi-native).
