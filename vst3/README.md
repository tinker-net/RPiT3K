# TON3K VST3 experimental preview

This is an unvalidated development build, not a finished port. It uses the original 48 kHz / 64-frame chain and portable NAM Core (not the Cortex-A76 Embedded implementation). Set the host to 48 kHz; other rates currently pass dry audio. Mono input (left on stereo tracks), duplicated mono output, 64 samples reported latency. Local NAM and mono WAV selection, two captures and two cabinet IRs, basic host parameters and project state (absolute file paths, not embedded). File changes are constructed on the message thread, not the audio callback; GUI may pause. The embedded original browser UI is experimental, with a native editor fallback. Cloud, calibration workflow, tuner, sample-rate conversion, reliable offline recall, validation and complete licensing review are not yet implemented. Do not assume realtime or host compatibility until tested. Keep levels low.

Build from repository root after cloning the pinned NAM Core and its submodules per rpi/README.md:
```sh
cmake -S vst3 -B build-vst3 -DCMAKE_BUILD_TYPE=Release
cmake --build build-vst3 --config Release --target TON3K_VST3
```
See GitHub Actions for unsigned/ad-hoc signed development artifacts if the build succeeds. Install the macOS bundle in ~/Library/Audio/Plug-Ins/VST3 or the Windows bundle in C:\Program Files\Common Files\VST3. Scan in Ableton, set 48 kHz and select a local capture. No commercial captures bundled.

The plugin combines MIT project source with JUCE 8 (AGPLv3 or commercial terms), NAM Core and DaisySP including LGPL-2.1 components. The existing project MIT notice is unchanged; combined binaries require compliance with all applicable dependency terms, including corresponding source and relinking rights. This branch is experimental; do not redistribute until licensing is reviewed. Source and build instructions are in this branch, and dependency revisions are pinned in CMake and the workflow.

## Linux preview (x86_64 and AArch64)

The same target builds VST3 and LV2 on Linux. Ubuntu 24.04 runners build native packages for both architectures. Requires a compatible glibc/system runtime and a graphical X11 host for the custom editor; WebKitGTK 4.1 is used for the original UI. The native fallback is also graphical. The LV2 DSP should be tested separately in headless hosts; PiPedal/MODEP do not automatically render JUCE's desktop editor in their browser interfaces. No PiPedal-specific web UI is included.

Dependencies on Ubuntu 24.04 / comparable Debian:
```sh
sudo apt install build-essential cmake pkg-config libasound2-dev libfreetype6-dev libfontconfig1-dev libx11-dev libxcomposite-dev libxcursor-dev libxext-dev libxinerama-dev libxrandr-dev libxrender-dev libgl1-mesa-dev libgtk-3-dev libwebkit2gtk-4.1-dev libcurl4-openssl-dev xvfb lv2-dev lilv-utils
cmake -S vst3 -B build-linux -DCMAKE_BUILD_TYPE=Release
xvfb-run -a cmake --build build-linux --target TON3K_VST3 TON3K_LV2 --parallel 2
```
After downloading and extracting the matching architecture package, install the complete TON3K.vst3 bundle under ~/.vst3/ or TON3K.lv2 under ~/.lv2/. LV2 URI: urn:tinkernet:ton3k. Set host to 48 kHz. Use a low monitoring level. Linux CI inspects bundle layout and LV2 metadata; this is not an audio or GUI runtime test. Ubuntu-built binaries are not guaranteed to run on older Debian or Raspberry Pi OS. Rebuild locally when necessary. Do not redistribute combined binaries until dependency licensing compliance is resolved.

## Logic Pro (Audio Units)

macOS also builds the AUv2 effect as TON3K.component for Logic Pro and GarageBand, with the same DSP and editor. Install the complete bundle under ~/Library/Audio/Plug-Ins/Components/. Set the project to 48 kHz for this preview. In Logic, rescan using Plug-in Manager if necessary and insert TinkerNet > TON3K as an Audio FX. Local build: cmake --build build-vst3 --config Release --target TON3K_AU. CI runs auval -v aufx T3k1 Tnkr after installing the ad-hoc signed component; passing this check is not equivalent to testing in Logic. macOS runner availability and runtime validation remain unconfirmed.

## Preview 0.2 development

The original Cubase-tested 0.1.0 is retained on branch native-preview-0.1.0. Library references and favorites are stored under TinkerNet/TON3K/library.json in the user application data directory. Folder import preserves relative paths, without copying or deleting source files. The browser caches unchanged controls and tree data; quick NAM selection targets the amplifier rather than the pedal. The pedal ON switch controls slot one only. Rig construction now runs on a dedicated worker; old audio continues until a replacement is prepared. These changes require host testing. The processor remains 48 kHz pending a validated sample-rate adapter; AU registration, portable presets, TONE3000 API and full plugin validation are outstanding. Reference architecture reviewed: TONE3000 MIT public repository, ProcessorModelLoader.cpp, ProcessorChain.cpp and Processor.cpp; background preparation and fixed base-rate processing are useful design principles. No upstream code copied.

Experimental host-rate adapter: keeps the original 48 kHz DSP and uses two precomputed windowed-sinc streaming converters for other host rates (8–384 kHz). The 48 kHz path remains unchanged. Reported host-domain latency includes a fixed FIFO prefill. Standalone identity-chain tests exercise sample count, phase alignment and continuity; actual DAW behavior remains to be validated. Use 48 kHz if any issues occur.

## Native 0.3 shared editor development
Branch native-unified based on a5d276c (latest standalone experimental source). CMake generates the Native editor directly from rpi/web.html with explicit adapter anchors, rather than building the historical plugin.html snapshot. NAM Core A2 fast, no Embedded. Hi-Z controls hidden and DSP forced off; legacy host parameter IDs retained for session compatibility. ADC reference is explicit, no PiSound assumption, and saved with project state; calibration uses Amplifier metadata. Local practice audio uses editor-memory file references and browser audio, waveform, speed/loops and browser metronome; not DAW-routed, persistent or transport-synced. Independent pitch shift and Guitar Pro are not yet enabled; tuner, full library operations, cloud, custom artwork, portable presets, host automation UI refresh and editor sizing require further work. No claim of full parity or DAW validation. All platform workflows build from native-unified. Do not publish as a final release.

## Native 0.3.1 development
Persistent local practice audio and Guitar Pro file imports use the native chooser and copy into TinkerNet/TON3K/practice-tracks and practice-scores in application data. alphaTab 1.8.4 assets are embedded by the build (npm required). DAW accompaniment mixes stereo after guitar FX at original speed and pitch, disabled for offline render; Local output uses WebView speed control, not routed through DAW. Independent transposition remains unimplemented. Track decoding is bounded to 128 MiB decoded stereo and happens on the message thread, not the audio callback; large tracks may stall the editor and are rejected beyond the cap. Audio callback never waits for the practice lock; contention can cause gaps. No sample-accurate looping or DAW transport synchronization. Native editor fills the full plugin window, with fallback only if WebView options unavailable; hardware-only maintenance and unsupported library actions hidden. Actual Cubase layout, WebView resource access, MIDI and native playback need acceptance tests. Host automation refresh is best effort; gestures and full library/portable presets remain open. This is a development preview, not a finished release.
