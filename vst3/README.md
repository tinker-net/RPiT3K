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
