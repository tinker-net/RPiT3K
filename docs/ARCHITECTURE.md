# Architecture

Three editions, one repository. The main branch is the project integration and documentation entry point.

| Path | Purpose |
| --- | --- |
| rpi/ | PiSound reference ALSA engine, browser controller, installation and integration |
| standalone/ | Standalone guide and pinned source reference; generic engine currently remains on rpi-general |
| vst3/ | JUCE desktop plugin wrappers, embedded UI and rate adapter |
| packaging/ | Debian package recipes for both Linux editions |
| docs/ | Roadmap, validation, architecture and history |
| app/, hardware/, embedded/, firmware files | Original upstream material, retained for provenance |

The standalone source currently differs in ALSA channel routing, controller defaults, installers and UI. Do not replace its server or installer with the PiSound version. The package builder uses immutable known source revisions. A future shared engine extraction must preserve both edition-specific defaults and existing services. Native's chain currently lives in rpi/plugin_chain.h; moving it into a common core requires regression and null tests, not merely relocating files.

## Target layout

- core: common DSP and model preparation
- ui: common frontend with host adapters
- platforms/pisound: ALSA plus physical controls and network integration
- platforms/standalone: generic ALSA routing and service
- platforms/native: JUCE wrappers
- packaging: build and distribution
- docs: user and developer documentation

This target is not the current physical layout. Keep existing build and installation paths until migration is tested.

## Release policy

Use immutable versioned releases for user downloads. Use CI artifacts for intermediate builds. Do not publish a stable designation without hardware/host tests. Keep source pins and SHA256 checksums with each Debian release. Preserve previously published assets and history.
