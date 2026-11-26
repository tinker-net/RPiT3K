# Native Linux engine — architecture and reproducibility

Current maintained editions: [Pisound](../README-PISOUND.md) (rpi-ui), [General ALSA](https://github.com/tinker-net/RPiT3K/tree/rpi-general) (rpi-general). Read [project status](../docs/PROJECT_STATE.md), [historical engine measurements](../docs/ENGINE_VALIDATION_2026-11-25.md) and [DaisySP validation](../docs/DAISYSP_VALIDATION.md) for evidence, not just feature claims.

## Architecture

C++20 production process, direct ALSA full duplex, 48 kHz S32_LE interleaved, mono guitar DSP, duplicated output to the selected channels. Pisound uses stereo capture/playback, left input and both outputs. General selects PCM, channel counts and one-based routing; one shared PCM, not separate unsynchronized devices. Supported period sizes 64/128/256/512 and counts 2/3/4. The period is N/48000 seconds (64 = 1.333 ms); 64×3 = 4 ms nominal buffer per direction, **not measured round-trip latency**. Requests SCHED_FIFO 60, falls back to normal scheduling. ALSA recovery count includes suspend recovery; CPU UI meter is whole-system utilization.

Signal path:

```text
ADC selected channel ──┬── input-keyed gate detector
                      └── Hi-Z → input gain → PRE compressor
                          → NAM A → NAM B → parallel IR A/B blend
                          → 3-band EQ → gate gain → POST compressor
                          → chorus → delay → ReverbSc → output gain → finite guard/clamp
                          → selected playback channels
```

The tuner uses input samples and mutes guitar output; metronome uses the sample clock, mixes after guitar effects, requires active audio and is muted in tuner mode. Gate is a continuous soft-knee downward expander, not a binary switch; downstream attenuation is keyed from raw input, with hold/release history (120/350 ms). Gate -81 means off; -80 to -30 dBFS active. EQ bass ±20, mid ±15, treble ±10 dB. Input amplitude 0–2, output 0–1. Bypass skips NAM and IR, **not** the remaining DSP. Output clipping guard is not an analog safety guarantee.

### NAM and IR

Pinned NAM Core d3189ed482ded880c128bf312941266c4fa5ceec, float32 interface, A2-fast build. TONE3000 Embedded v2.0.0 (Cortex-A76 engine) handles exact compatible 48 kHz mono A2 Full (8 channels) / Lite (3 channels) signatures including selected slimmable children. A1 and other Core-supported models fall back to Core; slots choose independently. Strict less-than slimmable breakpoint rule; fixed models do not become smaller by selecting Lite. Native .nam, not .namb. Force Core with RPIT3K_NAM_ENGINE=core or compile with -DRPIT3K_EMBEDDED=OFF. Backend selection appears in logs as NAM_ENGINE=embedded/core. No guarantee for arbitrary captures or sample rates. See historical null tests for tested examples.

Either NAM slot can be used alone; a second-only NAM runs in stage A with its own quality. Two NAMs run serially in stored order. Legacy second-slot WAV is still accepted; use dedicated IR slots for new rigs. Each mono WAV IR supports up to 48,000 taps **after resampling** at 48 kHz, source rates 8–384 kHz subject to WAV loader support. Windowed-sinc resampling compensates DC gain by sample-rate ratio; no automatic loudness normalization. Uniform 64-sample FFT partitions regardless of host period, all taps retained, two IRs parallel linear blend (not cascaded). No extra callback delay from partitioning; physical latency not measured.

### Calibration and effects

Input calibration is explicit: ADC reference dBu minus selected capture input_level_dbu, amplitude = 10^(dB/20). Applies global input gain for first active NAM (either slot), with slimmable child metadata and root fallback. Missing/invalid metadata or reference and out-of-range gain are reported, not guessed. Pisound +1.14 dBu is a nominal starting estimate at minimum analog gain; measure/adjust for actual interface and gain. General starts unknown and clears reference on input routing change unless a different reference is supplied. No automatic inter-stage gain staging, analog measurement or loudness normalization.

Hi-Z is an optional circuit-model correction from assumed 100 kΩ load to nominal 1 MΩ, not physical impedance conversion. Four pickup profiles; disable with appropriate buffer/native high impedance. Allow headroom. See historical circuit validation.

| Effect | Controls and implementation |
|---|---|
| Compressor | DaisySP-LGPL Compressor; Amount maps threshold -12 to -36 dBFS and ratio 1–6:1, attack .005 s, release .15 s, no makeup; PRE or POST NAM (post actually after IR/EQ/gate) |
| Chorus | DaisySP MIT ChorusEngine; 12 ms base delay, rate .1–5 Hz, depth 0–1 (upstream clamp .93), mix 1–100% while enabled; full mix is upstream 50/50 dry/wet |
| Delay | DaisySP MIT DelayLine; 20–1000 ms, feedback 0–85%, fractional interpolation and smoothed delay time |
| Reverb | DaisySP-LGPL ReverbSc, stereo averaged to mono; Dark/Bright/Neutral damping 3800/10000/6200 Hz; calibrated nominal .3–5 s broadband T30 RT60 |
 
All four have independent Enable switch, remembered amount and disabled controls while off; zero effective amount bypasses the DSP. Parameters and enables persist per preset. Smoothed fades; disabling drains internal state but does not promise audible spillover. Structural changes reset effect/NAM/IR histories. See [DaisySP source/license details](vendor/daisysp/README.md).

### Controller and live exchange

Python standard-library HTTP controller serves rpi/web.html and owns presets, files and native process. Audio always starts OFF, even with deprecated --autostart. Last selected preset is retained; edits while stopped do not open ALSA. Four slots autosave. Ordinary gain/effect edits sent over bounded stdin controls (20 numeric fields, METRO separate); structural changes sent on separate rig request/ack pipes. Worker constructs and retires rigs outside audio callback; atomic pointer exchange at block boundary, 64 samples fade-out/in. Invalid replacement retains old rig. Not gapless, no spillover guarantee. Hardware setting changes reopen ALSA when active; tuner is distinct mode. No plugin host, JACK, PipeWire, MIDI, original USB Companion integration or multichannel guitar processing.

Browser: fixed TONE3000-inspired skin, six amplifier knobs, peak meters, CPU/temp/buffer/xruns, effect dialogs and device toolbar, collapsible/resizable library and rig sidebars, search, real nested folders, favorites, rename/move with preset reference migration, confirmed permanent deletion, custom WebP amp-family artwork. Layout and artwork choice stored locally in browser, artwork files on server. Audio status green when running, effects yellow when enabled; power menu separate, optional.

### Persistent data and security

Pisound ~/.local/share/rpit3k; General ~/.local/share/rpit3k-general. Includes presets.json, settings.json, favorites.json, library/, amp-art/, and optional tone3000-session.json (private 0600, atomic replacement). OAuth device authorization uses a publishable key, stores access/refresh tokens and wall-clock expiry, refreshes on demand, handles rotated token and manual logout. Offline tests mock network; real server/reboot still unverified. Keep credentials private; don't publish the data directory. No secret key. Service defaults loopback/no-auth/cloud disabled; direct manual server defaults to HTTP Basic auth unless --no-auth, cloud enabled unless --disable-cloud. Never expose unauthenticated LAN or optional host power actions to untrusted clients. API mutation requires X-RPiT3K: 1. Local cloud is separate from original Daisy Companion; no claims of official endorsement or API compliance certification.

## Build and verification

From repo root, normal user, stop appropriate audio service before timing or rebuilding:

```sh
sudo apt install git build-essential cmake libasound2-dev alsa-utils python3 curl ca-certificates
git clone https://github.com/sdatkinson/NeuralAmpModelerCore.git
git -C NeuralAmpModelerCore checkout d3189ed482ded880c128bf312941266c4fa5ceec
git -C NeuralAmpModelerCore submodule update --init --recursive
cmake -S rpi -B build-rpi -DCMAKE_BUILD_TYPE=Release
cmake --build build-rpi -j2
ctest --test-dir build-rpi --output-on-failure -V
./build-rpi/rpit3k --bypass --verify
```

Skip clone if already checked out; do not overwrite local changes. Pi 5 may add -DRPIT3K_CPU=cortex-a76, Pi 4 cortex-a72. Embedded fetch uses v2.0.0 tag, not a content hash; network needed for first build. CMake warns about legacy FetchContent_Populate on 3.31; nonfatal. Shared librpit3k-daisysp.so must remain available (build-tree RPATH). Do not distribute standalone binary without library and licenses.

### Additional reproduction (offline, no ALSA)

```sh
cmake --build build-rpi --target nam-reference -j2
python3 rpi/null_test.py /path/to/capture.nam
python3 rpi/hybrid_test.py /path/to/A2.nam /path/to/A1.nam
python3 rpi/hiz_test.py build-rpi/rpit3k
# independent IR validation requires numpy and scipy (e.g. apt python3-numpy python3-scipy)
python3 rpi/ir_test.py
./build-rpi/rpit3k --model /path/to/amp.nam --ir /path/to/cab.wav --benchmark
```

Commercial models/IR not bundled. Null/hybrid tests require user-provided compatible captures; hybrid test requires Embedded enabled. Optional hybrid --ir and --ir2. Offline renderer expects nonempty little-endian float32 files aligned to whole host blocks, refuses existing output. --verify measures gain, mute and EQ with synthetic signal, **resets effect controls** during verification; it is not an enabled-effects test. --benchmark measures per-block Chain wall time, excludes ALSA and model load, not real-time certification.

## Testing map

| CTest group | Scope |
|---|---|
| practice_metronome | sample timing, gain, mute, bypass |
| capture_calibration | metadata/reference and gain rules |
| native_dsp | Hi-Z, gate, convolution, tuner and basic effects |
| live_rig_exchange | synthetic worker exchange and rejection |
| daisysp_characterization | static compressor, delay echoes, chorus modulation, 24 calibrated reverb points, automation timing |
| tonecloud_session | 8 mocked OAuth persistence/refresh cases |
| effect_preset_state | 5 migration/bypass/live/disk checks |
| production_chain | synthetic identity NAM, second-slot routing, dual IR and bypass through actual executable; Pi 5 PASS at bf45495; identity-model smoke test, not nonlinear stage-order proof |

Python tests require Python3 interpreter; install it to obtain complete suite. CI builds ARM64 and x86-64, runs CTest, bypass verification and script checks; workflow outcomes must be inspected before claiming CI passes. Neither CI nor synthetic tests replace real interface tests.

For real hardware, record commit, compiler, kernel, device/channels, period, capture/IR hashes, duration, temperatures, DSP mean/max/late counters and ALSA recoveries. Compare before/after enabling effects, single/dual captures and IRs, preset changes, sustained notes, tuner/metronome, restart/reboot OAuth. Keep logs free of credentials. Historical measurements are not benchmarks of each new commit.
