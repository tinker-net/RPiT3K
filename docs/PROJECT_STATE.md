# RPiT3K — current project state

Updated 2026-11-26. Current source and validation scope, not a release certification.

## Maintenance
- rpi-ui: primary Pi 5/Pisound source edition; rpi-general: same shared features with configurable ALSA and separate data/service. Keep both in sync, preserve hardware differences. No new branches without maintainer request.
- live-rig is historical; deb-packaging maintains immutable pins for both source editions and five package variants. Original Daisy firmware, hardware and app are separate inherited upstream components.
- [User guide](../README-PISOUND.md), [technical architecture](../rpi/README.md), [historical engine measurements](ENGINE_VALIDATION_2026-11-25.md), [current DaisySP evidence](DAISYSP_VALIDATION.md).

## Current evidence
Pi 5/Pisound, aarch64 Linux 6.18.60+rpt-rpi-2712, GCC 14.2.0: incremental build and 8/8 CTest PASS at bf454958beece27f884513d0f9ff7b7f9d06270a, 3.48 s. 24/24 calibrated RT60 points; max absolute error .04174815 s, relative .06388795; compressor max curve error .004901886 dB; integer delay echo timing exact in tested cases; chorus modulation/bypass tested; 8 mocked OAuth and 5 effect state tests. Combined synthetic FX automation 10 s processed in .09209452 s; not ALSA timing. Native IR max absolute error 3.97309e-7, tuner max 2.66869 cents. Historical 16/16 hybrid null tests and short live Pi runs are older evidence, not retested at this HEAD.

## Current behavior
- Audio always OFF at service start. Persistent four slots, independent NAMs, two parallel IRs, live worker exchange with fade/reset (not gapless); invalid replacement preserves old rig.
- Input-keyed expander, EQ and gains, optional Hi-Z and explicit Amplifier-only NAM calibration, native DaisySP compressor/chorus/delay/ReverbSc, practice metronome and tuner.
- Single web skin, independent collapsible sidebars, library folders/favorites and artwork, effect switches with remembered values, device controls and optional power menu. OAuth saved in private file, cloud disabled by service installers unless explicitly enabled.
- New consolidation fixes installer readiness to require controller available and audio stopped; no unattended live audio test. Power helper allows exact poweroff/reboot commands only after explicit opt-in. Existing installations must rerun helper to grant reboot. Production-chain regression passed on Pi 5 (0.08 s, max blend residual 1.3981e-7); updated CI checks not independently verified.

## Open validation
Clean SD installation, real browser rendering, live audio stability/latency and audible transitions with latest effects, hardware button/hotspot, real OAuth authorization/download/restart/reboot, generic USB/x86 hardware, and physical ADC/Hi-Z measurement. Documentation and code inspection do not establish these results. No changes to DSP algorithms in documentation consolidation.

## Independent cabinet and second NAM bypass
Each preset stores independent `bypass_nam2` and `bypass_ir` switches; NAM 1 retains its existing stomp. IR bypass excludes both cabinet IRs including legacy WAV in slot 2. Structural changes use the existing live rig exchange and fade, without reopening ALSA. Legacy global bypass migrates to NAM 1 OFF and both bypass switches ON. No inference or convolution algorithm changes. Added controller routing/migration and production offline signal checks; CI and hardware verification pending.

## Current shared controls and library

- **Pedal (NAM 1):** independent stomp with a 10 ms transition; its state is saved per preset. **Amplifier (NAM 2):** separate bypass. **Bypass IR:** disables both cabinet IRs, including a legacy WAV in slot 2. Captures remain selected and can be re-enabled. Structural changes use the existing live exchange and short fade; no gapless/spillover guarantee.
- **Input calibration:** uses only the selected Amplifier NAM and its selected slimmable child/root metadata, never the Pedal. Applies the global pre-pedal input gain explicitly; no automatic inter-stage calibration. No amplifier or valid metadata/reference means no automatic correction. The amplifier remains the reference even when bypassed.
- **Six knobs:** prominent 0–10 position plus editable technical dB underneath. Input 5 = unity, output 5 = half amplitude (about -6.02 dB), EQ 5 = 0 dB; gate OFF is the -81 sentinel. The scale is linear in the existing parameter, not a new gain curve. Input 0 and output 0 are silence. Drag normally, Shift-drag for 10× lower sensitivity, wheel for increments; focus/double-click the dB readout, Enter/blur to apply, Escape to cancel. Existing parameter ranges and quantization remain (input amplitude 0–2, step 0.000001; output 0–1, step .01; gate/EQ integer dB). Display rounding is not a new preset format.
- **Capture picker:** search filenames and folders using unordered AND terms, abbreviation expansion (FNDR/Fender, MRSHL/Marshall, BFSR/Super Reverb, CLN/Clean, WRM/Warm, etc.), inferred family tags and relevance sorting. Examples: `fender clean fat`, `marshall crunch`, `blackface warm`. Quick filters vary by Pedal, Amplifier and IR; Favorites narrows results. Classification is heuristic, not audio analysis. Optional **Index metadata** reads local NAM metadata sequentially while audio is stopped; results are browser-session cached, not persisted. Closing the picker stops further indexing. A2 matching depends on available text/metadata; architecture alone does not establish model generation.
- **Notifications:** contextual toast stack, success/info 3 s, warnings 6 s, errors and progress until dismissed/replaced (maximum five visible per stack). Dialog validation and ongoing import/cloud progress remain inline. No persistent Rig Details message.
- **Artwork:** custom family-named WebP (maximum 2 MiB); Rams Head, Kingsley Page, Twin Bender and Octavio families included. Import `ramshead.webp`, `kingsleypage.webp`, `twinbender.webp`, `octavio.webp` for custom images; no commercial images or captures supplied. Selection stored locally per capture.
- Shared UI changes require no native rebuild. For source installations pull the correct branch, restart its service and hard-refresh the browser; audio restarts OFF. Rebuild and run regression tests whenever native code/dependencies change.

## Latest integration evidence and remaining risks (2026-11-26)

Maintainer reports successful everyday operation of the current PiSound development setup; this is qualitative, not a timed stress test. The HTTP port 80 migration reported controller ready with audio OFF. GitHub Actions completed successfully for [PiSound 0275920](https://github.com/tinker-net/RPiT3K/actions/runs/45853761283), [General 37952ec](https://github.com/tinker-net/RPiT3K/actions/runs/45853771542) and [Debian packages 8ab4841](https://github.com/tinker-net/RPiT3K/actions/runs/45853780731). These runs do not certify browser interaction, electrical/analog behavior, physical button timing, or installation on every target.

Suggested acceptance checks:
1. Back up private data, start at low monitor volume. Play 60–120 minutes at 48 kHz / 64×3 with two demanding NAMs, two long IRs and effects; check xruns, temperature, logs, audible interruptions, gain/clipping and memory growth. Repeat preset/bypass changes and compare with a larger buffer if necessary.
2. With distinct saved presets, test rapid but deliberate physical clicks/holds, browser changes and reconnects. Verify LED slot count, stomp isolation, audio OFF after reboot and no unintended shutdown. Simultaneous browser clients/button changes may expose stale preset state or last-write-wins conflicts.
3. Test Wi-Fi/Ethernet loss, manual hotspot off/on and recovery after reboot; confirm hostname and direct IP access, port conflicts, and no unintended fallback takeover. LAN HTTP is unauthenticated when explicitly enabled; keep on trusted networks only.
4. Exercise large NAM libraries, corrupted/unsupported models, missing metadata, favorite/rename/move/delete, duplicate imports, exact dB editing/Shift-drag and cancel, mobile/small-screen dialogs, and repeated notifications. Metadata cache can become stale if files are replaced under the same name; search aliases can overmatch; metadata parsing under the controller lock may delay requests. Recheck all six controls after saving/reloading presets.
5. Test cloud expiry/refresh, offline startup and interrupted downloads. Test generic ALSA channel mapping, unsupported formats and USB unplug/replug; automatic recovery is not guaranteed. Test clean package installation, removal, rollback and data preservation on spare media; do not overwrite a working installation merely to test.
6. Verify calibration and Hi-Z against actual hardware/analog gain; global gain affects both NAMs, and output level can jump between captures. DSP buffer duration is not analog round-trip latency.

No new DSP measurement or physical test is claimed by this documentation change.
