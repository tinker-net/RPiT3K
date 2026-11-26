<div align="center">

# TON3K

**Neural Guitar Processing Platform**

Independent, open-source NAM guitar processor for dedicated hardware, Linux and desktop DAWs.

[Downloads](#downloads) · [Documentation](#documentation) · [Roadmap](docs/ROADMAP.md) · [Changelog](CHANGELOG.md)

</div>

---

## TON3K PiSound

A dedicated guitar rig for Raspberry Pi 5 and Blokas PiSound. Browser control, physical button gestures, optional hotspot, four presets and offline audio processing. Current PiSound source includes Practice Mode, smart NAM/IR library and offline backup. [Validation and rollback](docs/PROJECT_STATE.md). Published DEBs are older snapshots.

[Installation guide](README-PISOUND.md) · [Debian packages](https://github.com/tinker-net/RPiT3K/releases/tag/deb-preview-54)

## TON3K Standalone

A hardware-independent Linux guitar processor for ARM64 and x86-64, using configurable ALSA input/output. No PiSound driver, button or hotspot dependency. Raspberry Pi 4/5 and compatible 64-bit Linux systems.

[Installation guide](README-GENERAL.md) · [Debian packages](https://github.com/tinker-net/RPiT3K/releases/tag/deb-preview-54)

## TON3K Native

The TON3K experience inside a DAW. VST3 for Windows, macOS and Linux; AU for macOS; LV2 for Linux. Native 0.1 was tested in Cubase on Apple Silicon; 0.2 is a development preview with successful CI builds, not yet host-validated.

[Plugin guide](vst3/README.md) · [Native downloads](#native-plugins)

---

**Shared direction:** one DSP core, consistent interface, shared library conventions and portable presets. Full convergence is a roadmap goal, not yet complete.

## Downloads

### Debian 13 / Raspberry Pi OS Trixie (64-bit)

The current published packages are experimental. Install only one variant; read the [package guide](packaging/README.md) before replacing an existing source installation.

| Edition | Target | Package |
| --- | --- | --- |
| PiSound | Pi 5 | [DEB](https://github.com/tinker-net/RPiT3K/releases/download/deb-preview-54/rpi-ton3k-pisound_0.1.0.preview54_arm64-cortex-a76.deb) |
| Standalone | Pi 5 | [DEB](https://github.com/tinker-net/RPiT3K/releases/download/deb-preview-54/rpi-ton3k_0.1.0.preview54_arm64-cortex-a76.deb) |
| Standalone | Pi 4 | [DEB](https://github.com/tinker-net/RPiT3K/releases/download/deb-preview-54/rpi-ton3k_0.1.0.preview54_arm64-cortex-a72.deb) |
| Standalone | ARM64 | [DEB](https://github.com/tinker-net/RPiT3K/releases/download/deb-preview-54/rpi-ton3k_0.1.0.preview54_arm64.deb) |
| Standalone | AMD64 | [DEB](https://github.com/tinker-net/RPiT3K/releases/download/deb-preview-54/rpi-ton3k_0.1.0.preview54_amd64.deb) |

[Release notes and SHA256 sums](https://github.com/tinker-net/RPiT3K/releases/tag/deb-preview-54)

### Native plugins

| System | Formats | Preview 0.2 CI artifact |
| --- | --- | --- |
| macOS Universal | VST3, AU | [ZIP](https://github.com/tinker-net/RPiT3K/actions/runs/45886130025/artifacts/15149044060) |
| Windows x64 | VST3 | [ZIP](https://github.com/tinker-net/RPiT3K/actions/runs/45886130025/artifacts/15149377294) |
| Linux x86-64 | VST3, LV2 | [ZIP](https://github.com/tinker-net/RPiT3K/actions/runs/45886130090/artifacts/15149417124) |
| Linux ARM64 | VST3, LV2 | [ZIP](https://github.com/tinker-net/RPiT3K/actions/runs/45886130090/artifacts/15150145838) |

These CI artifacts require GitHub login and expire. Native release publication is a separate manual promotion step after license compliance and host validation. macOS is ad-hoc signed, not notarized; AU registration is not yet confirmed. PiPedal does not automatically display the desktop LV2 editor.

## Documentation

- [PiSound](README-PISOUND.md)
- [Standalone](README-GENERAL.md)
- [Native plugins](vst3/README.md)
- [Debian packaging](packaging/README.md)
- [Architecture and source map](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Validation evidence](docs/PROJECT_STATE.md)
- [Historical source revisions](docs/SOURCE_HISTORY.md)

## Project status

PiSound is the reference hardware. Standalone uses its own validated source snapshot pending full integration. Native shares DSP components but still has a separate chain implementation. No personal captures, API credentials or commercial IRs are distributed.

## Credits and licensing

Inspired by [TONE3000 × Daisy DIY Pedal](https://github.com/tone-3000/t3k-diy-pedal). This is an independent project, not an official TONE3000 product. Original firmware, hardware and companion are preserved for provenance; [upstream README](README-DAISY.md). See [LICENSE](LICENSE), [DaisySP notices](rpi/vendor/daisysp/README.md) and [artwork notice](UI-TONE3000-LICENSE.txt). Plugin redistribution requires review of JUCE and LGPL obligations. Capture and IR rights remain with their authors.
