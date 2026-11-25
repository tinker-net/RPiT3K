# RPi-Ton3K General

Current rpi-ui DSP and web interface, adapted for Linux ALSA interfaces on ARM64 and x86-64. Experimental: not yet compiled or tested on x86-64 or physical USB audio by the maintainer. Raspberry Pi OS / Debian / Ubuntu with systemd and 64-bit userspace are installer targets. 32-bit systems are not supported. Other Linux distributions require equivalent dependencies and manual CMake build.

## Install

Stop any existing RPiT3K service before installing. Use a separate checkout, as both branches build to build-rpi.

```bash
sudo apt update
sudo apt install -y git
git clone --branch rpi-general https://github.com/tinker-net/RPiT3K.git RPiT3K-General
cd RPiT3K-General
aplay -l
arecord -l
bash rpi/install-general.sh
```

This installs compiler, ALSA and Python dependencies, pins NAM Core, builds, executes offline regression tests and installs rpit3k-general.service. Local data lives in ~/.local/share/rpit3k-general, separate from Pisound edition. Existing settings are preserved when reinstalling. The default PCM is default, with 256 frames and three periods, capture channel 1 and two playback outputs. Audio readiness is checked using live meters; a controller may be installed successfully while hardware configuration is still required.

## Configure interface

Use an SSH tunnel from another machine:
```bash
ssh -N -L 8080:127.0.0.1:8080 USER@HOST
```
Open http://localhost:8080. Expand Audio settings & diagnostics, scan devices, choose the same duplex ALSA PCM for capture/playback, configure channels and press Apply audio settings. If audio is stopped, press Start to test a preset. A failed restart attempts to restore prior settings.

Example for a two-channel Scarlett with guitar on input 2 (replace CARD with actual ALSA card ID from aplay/arecord):
```bash
bash rpi/install-general.sh --device plughw:CARD=USB,DEV=0 --input-channel 2 --buffer 256
```

The example ID USB is a placeholder, not a detected Scarlett ID. On multichannel interfaces set --input-channels and --output-channels to supported counts, then choose --input-channel, --output-left, --output-right (one-based). For mono output choose both output channels as 1 and output count 1. Unselected outputs receive silence. A single shared PCM is used; separate unsynchronized audio interfaces are not supported. Direct hardware monitoring should be disabled to avoid mixing processed and dry signals. Lower output volume before starting.

hw: uses direct hardware access; plughw: allows ALSA format/channel/rate conversion if needed. The application requests 48 kHz S32_LE and exact buffer/period geometry; incompatible configurations may be rejected. Try 128, 256 or 512 frames, 2–4 periods or an appropriate ALSA PCM. Not every driver/interface exposes compatible full-duplex streaming. No automatic hotplug recovery is promised.

## Calibration

Set ADC full-scale reference in dBu for the actual interface and analog gain position, then use Calibrate Input to read NAM input_level_dbu metadata. No generic reference is assumed. Changing input routing invalidates an unchanged stored reference. Recalibrate after changing analog gain. No automatic physical voltage measurement is performed.

## Access and service

Default is localhost, no authentication, cloud disabled. For trusted isolated LAN only, add --lan at installation; never expose port 8080 to the Internet. --cloud is experimental and not validated. No Pisound driver, button or hotspot is automatically installed. For a dedicated Pisound installation use rpi-ui.

```bash
sudo systemctl status rpit3k-general
sudo journalctl -u rpit3k-general -n 100 --no-pager
```

Updates: stop service, git pull --ff-only origin rpi-general, rebuild, run ctest and --bypass --verify, then start service. To uninstall, disable and remove rpit3k-general.service and reload systemd; preserve or back up local data.

## Validation

The existing Pi 5 DSP results are documented in the main README and are inherited, not new measurements for this branch. Compile and run regression tests on each architecture, verify selected capture and output routing, measure live xruns and timing, and test analog latency and calibration. Performance and compatibility with arbitrary interfaces cannot be guaranteed by class compliance alone.

## Optional host shutdown button

After installing the service, run `bash rpi/install-poweroff.sh` as its normal user and confirm. The top-left power button asks for confirmation before stopping audio and requesting a systemd poweroff. The helper installs a root-owned sudoers rule limited to the exact poweroff command and a service environment flag. On unauthenticated LAN mode, anyone with API access can shut down the host: enable only on a trusted isolated network. Disable with `bash rpi/install-poweroff.sh --disable` before uninstalling the service. The button does not physically disconnect power or switch the device back on.

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

