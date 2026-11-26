# Roadmap

## Reference baseline
PiSound: existing tested source installation; Debian preview 54 has CI validation, not a physical package installation test.
Standalone: separate generic ALSA edition with no PiSound dependency.
Native 0.1: Cubase on Apple Silicon confirmed GUI and initial NAM/IR processing.

## Native 0.2
Persistent library references and favorites, recursive folder import, reduced UI redraws, background rig loading, experimental rate adapter. CI builds passed on macOS, Windows and Linux x86-64/ARM64; host tests pending.

## Next milestones
1. Test Native controls, effects, preset restore, resampling and multiple instances in real hosts.
2. Resolve AU registration, plugin validation and distribution licensing.
3. Complete folder operations, drag/drop, tuner, calibration and optional TONE3000 API.
4. Define a portable versioned preset bundle with capture/IR references and optional assets.
5. Extract shared DSP and frontend contracts with regression tests for all editions.
6. Consolidate standalone source into a common engine with separate hardware adapters.
7. Promote named releases with notes and checksums; keep CI builds distinct from releases.
