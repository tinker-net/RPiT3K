# RPi-Ton3K for Blokas Pisound

An independent, experimental Raspberry Pi guitar processor derived from the TONE3000 × Daisy DIY Pedal project. This guide is for the native Pisound edition, not the Daisy firmware. No affiliation with Blokas or TONE3000 is implied.

## What it does

- Native Neural Amp Modeler (NAM Core), one or two mono NAM captures, optional mono cabinet WAV IR, three-band EQ, input/output gain and input-keyed soft-knee noise reduction.
- Browser-controlled four presets, live gain/EQ/gate controls, chromatic tuner, input/output peak meters, ALSA recovery counter and CPU/temperature monitoring.
- Direct ALSA, 48 kHz, left input and dual mono output. No JACK, LV2 or PipeWire required.
- Optional Pisound button preset cycling, systemd autostart and offline Wi-Fi hotspot.
- Local captures work offline. TONE3000 account browsing/import is experimental, disabled by default on new service installations and not yet end-to-end verified; use local file import.

## Compatibility

| Platform | Status | Initial buffer |
| --- | --- | --- |
| Raspberry Pi 5, 64-bit Raspberry Pi OS Lite (Trixie), Pisound | Developer-tested DSP and live audio; fresh automated install not yet tested | 64 × 3 |
| Pi 4 / CM4 / Pi 400 with compatible Pisound mounting, 64-bit Raspberry Pi OS | Candidate, not hardware-tested | 128 × 3 |
| Pi 3 / Zero 2 W and other 64-bit Pi models with compatible Pisound | Experimental, CPU/RAM may be insufficient; no real-time guarantee | 256 × 3 |
| 32-bit OS, Pi 1/2/Zero, Pisound Micro, other distributions | Not supported by this installer |

Use a reliable power supply, adequate cooling and preferably at least 2 GB RAM for compiling. A successful build does not guarantee every model will run in real time. Verify physical compatibility with [Blokas specifications](https://blokas.io/pisound/docs/specs/). No measured analog round-trip latency claim is made.

## Fresh installation

Install Raspberry Pi OS Lite **64-bit** with Raspberry Pi Imager. Configure your own username, network and SSH. Power off before attaching the Pisound. Boot and connect via SSH or terminal as the normal sudo-enabled user (not root).

```bash
sudo apt update
sudo apt install -y git
git clone --branch rpi-ui https://github.com/tinker-net/RPiT3K.git
cd RPiT3K
bash rpi/install-pisound.sh --install-blokas
sudo reboot
```

The explicit Blokas step downloads and runs the vendor's current installer from [official documentation](https://blokas.io/pisound/docs/the-pisound-software/). It may ask questions or update system configuration. If already installed, skip this step. Inspect the vendor script first if desired; it is maintained externally and not pinned.

After reconnecting, confirm the card appears in both directions:

```bash
aplay -l
arecord -l
cd ~/RPiT3K
bash rpi/install-pisound.sh
```

The second step installs build dependencies, checks the card, checks out pinned NAM Core and its submodules, selects CPU flags for the detected Pi, compiles locally, runs CTest and offline verification, and installs/enables the systemd service only after the tests pass. A subsequent readiness check requires live audio telemetry before reporting success. It preserves existing presets, captures and audio settings. It needs Internet for installation, not for local playing.

### Browser access

Default: loopback only. From another computer, substitute your actual username and Pi address:

```bash
ssh -N -L 8080:127.0.0.1:8080 USER@PI_ADDRESS
```

Open http://localhost:8080. For a dedicated trusted LAN or fallback hotspot, explicitly opt in to network access:

```bash
bash rpi/install-service.sh --lan
```

Then open http://PI_ADDRESS:8080. **LAN mode is unauthenticated HTTP; anyone on that network can operate the pedal and access the connected cloud session. Never expose port 8080 to the Internet or an untrusted network.** Keep loopback mode for shared networks. No public API key, account credentials or Wi-Fi password is bundled.

### Experimental cloud integration

For private development testing only, add --cloud to the service installer (prefer loopback access). A personal publishable key is required; never enter a secret key. Public distribution of the enabled integration must first meet [TONE3000 API terms and design requirements](https://www.tone3000.com/api/terms) and complete end-to-end authentication/download testing.

### Physical button and hotspot (optional)

```bash
bash rpi/install-service.sh --lan --button
```

This explicitly replaces the single-click action in /etc/pisound.conf, preserving a backup at /etc/pisound.conf.rpit3k-backup; other actions are left untouched. Omit --lan for SSH-only access. Physical button integration still needs independent hardware confirmation. Restore the original configuration from the backup only if appropriate (it may predate subsequent custom changes), then restart pisound-btn.

On NetworkManager systems with Wi-Fi, optionally run:

```bash
bash rpi/install-hotspot.sh
```

Enter your own WPA2 password when prompted. Requires LAN mode to use the web UI. Fallback SSID RPiT3K, address http://10.42.0.1:8080; activates when no Ethernet/Wi-Fi connection is active. It stays active until disconnected or rebooted. Not suitable for every networking setup; optional and not installed by default.

## First use

Start with the physical monitor volume low. Stop other applications that exclusively open Pisound; the installer does not disable JACK, PipeWire, MODEP or PiPedal. Import your own compatible .nam and mono .wav (up to one second after resampling to 48 kHz), select a preset, capture and optional IR, disable bypass and press Start. Choose Full for fixed models; Lite is only for compatible slimmable models. Begin with low output and gate OFF. Adjust input for the capture's calibration; automatic analog calibration is not implemented. Model/preset changes restart audio and are not gapless. No captures or commercial IRs are supplied.

If xruns occur, increase period size or periods in Audio settings. The counter includes ALSA suspend recovery and is cumulative since service start. The displayed buffer duration is per direction, not measured round-trip latency.

## Updates and troubleshooting

```bash
cd ~/RPiT3K
git pull --ff-only origin rpi-ui
sudo systemctl stop rpit3k
cmake --build build-rpi -j2
ctest --test-dir build-rpi --output-on-failure
./build-rpi/rpit3k --bypass --verify
sudo systemctl start rpit3k
```

Run the guided installer again for dependency/CPU configuration changes; repeat your desired --lan/--button options (and --cloud only for development). Existing audio settings are retained. Use --jobs 1 on low-memory machines. Check the browser diagnostics and:

```bash
sudo systemctl status rpit3k
sudo journalctl -u rpit3k -n 100 --no-pager
aplay -l
arecord -l
```

If Pisound is missing, consult Blokas and run sudo pisound-config; reboot if required. If the service starts but audio does not, inspect the browser logs (the service can be up even when ALSA fails). Do not post credentials or private logs without redaction.

## Uninstall

```bash
sudo systemctl disable --now rpit3k
sudo rm /etc/systemd/system/rpit3k.service
sudo systemctl daemon-reload
```

If installed, disable the hotspot timer and remove the RPiT3K-fallback connection via nmcli; restore the button action as described above and remove /usr/local/bin/rpit3k-next. Blokas software and other applications are intentionally left installed. Your local data remains in ~/.local/share/rpit3k; back it up before deleting it. The source checkout can then be removed.

## Validation and license

See [technical report and reproducible tests](rpi/README.md). On Pi 5 the latest native DSP suite and bypass verification passed, including the soft-knee expander. Full/Lite NAM and IR numerical comparison results refer to earlier tested builds. Long sessions, final integrated performance, fresh installation, other Pi boards, physical button and live cloud login/download still require testing. This is a preview, not a production-certified pedal.

Original project and reused EQ: TONE3000 × Daisy DIY Pedal, [MIT license](LICENSE). NAM Core and its dependencies retain their own licenses. Capture/IR authors retain their rights; do not redistribute downloaded or commercial assets without permission. TONE3000 API usage is subject to its terms; the optional integration is not a claim of official endorsement.

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

