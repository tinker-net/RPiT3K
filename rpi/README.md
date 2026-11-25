# RPiT3K native prototype

Experimental Linux port for Raspberry Pi 5 + Pisound. Original Daisy firmware is untouched.
This first milestone implements a command-line audio chain and offline timing benchmark; it is not a finished pedal.

## Build on 64-bit Raspberry Pi OS / Debian

From the repository root:

```sh
sudo apt install git build-essential cmake libasound2-dev
git clone https://github.com/sdatkinson/NeuralAmpModelerCore.git
git -C NeuralAmpModelerCore checkout d3189ed482ded880c128bf312941266c4fa5ceec
git -C NeuralAmpModelerCore submodule update --init --recursive
cmake -S rpi -B build-rpi -DCMAKE_BUILD_TYPE=Release
cmake --build build-rpi -j2
```

## Benchmark before opening audio

```sh
./build-rpi/rpit3k --model amp.nam --slim 1 --benchmark
./build-rpi/rpit3k --model amp.nam --slim 0 --benchmark
./build-rpi/rpit3k --model amp.nam --second cab.wav --benchmark
```

The 64-frame deadline at 48 kHz is 1333 us. Benchmark reports average and worst processing time, not round-trip latency or xrun-free operation. Leave considerable headroom. Slim 1 selects maximum size; 0 selects minimum in compatible slimmable models. No automatic downgrade. For classic fixed-size NAM files omit --slim. A second NAM has its own --slim2.

## Audio trial

Stop PiPedal before opening Pisound; lower monitor/headphone volume. Input is left channel, output is dual mono. No automatic analog calibration yet.

```sh
./build-rpi/rpit3k --device hw:pisound --model amp.nam --second cab.wav --output 0.15
```

The prototype requests 48 kHz, stereo S32_LE, 64 frames, 3 periods; unsupported settings fail explicitly. It stops on xruns instead of silently continuing. ALSA startup/synchronization, physical latency, and model throughput need testing on actual hardware.

## Roadmap

- Reliable full-duplex startup, xrun recovery, realtime scheduling, telemetry and benchmarks.
- Gain staging calibrated against Pisound's physical input (not Daisy's +2.2 dBu), optional normalization, gate.
- Partitioned IR convolution if Core's WAV loader is insufficient for timing.
- Preset storage, safe model changes, MIDI, systemd service.
- Adapt React app to LAN API; retain TONE3000 integration and add local NAM/WAV imports and per-block quality control.

The CLI engine has been compiled and tested with Pisound on a Raspberry Pi 5; a real slimmable capture ran successfully. Long-session stability and IR throughput remain unverified. MIDI is not implemented yet.

## Local web controller (preview)

From the repository root, run as your normal audio-enabled user:

```sh
python3 rpi/server.py
```

For secure access from a Mac, open a second Mac terminal and run:

```sh
ssh -N -L 8080:127.0.0.1:8080 tinkernet@HWW-RPiT3K.local
```

Open http://localhost:8080 in a browser and enter the username and generated password printed on the Pi terminal. For a trusted isolated LAN you can instead launch with `--bind 0.0.0.0`, but HTTP Basic authentication is not encrypted over LAN; do not expose it to the Internet. No root web server. The audio engine may warn that realtime scheduling is unavailable until the audio user's limits are configured. Stop any existing CLI audio process first.

Import local NAM/WAV files, select a preset, choose a capture, uncheck bypass, and Apply. Four presets persist under ~/.local/share/rpit3k. Full is the default for slimmable models. Controls apply on restart, not continuously; switching interrupts audio and runs an offline validation benchmark first. No TONE3000 account integration yet. Web controller is untested on the Pi.
