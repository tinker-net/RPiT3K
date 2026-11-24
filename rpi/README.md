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

No web server or MIDI service is implemented yet. This prototype has not been compiled or tested on Pisound.
