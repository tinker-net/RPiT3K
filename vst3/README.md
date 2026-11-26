# TON3K VST3 experimental preview

This is an unvalidated development build, not a finished port. It uses the original 48 kHz / 64-frame chain and portable NAM Core (not the Cortex-A76 Embedded implementation). Set the host to 48 kHz; other rates currently pass dry audio. Mono input (left on stereo tracks), duplicated mono output, 64 samples reported latency. Local NAM and mono WAV selection, two captures and two cabinet IRs, basic host parameters and project state (absolute file paths, not embedded). File changes are constructed on the message thread, not the audio callback; GUI may pause. The browser UI, cloud, calibration workflow, tuner, sample-rate conversion, reliable offline recall, validation and complete licensing review are not yet implemented. Do not assume realtime or host compatibility until tested. Keep levels low.

Build from repository root after cloning the pinned NAM Core and its submodules per rpi/README.md:
```sh
cmake -S vst3 -B build-vst3 -DCMAKE_BUILD_TYPE=Release
cmake --build build-vst3 --config Release --target TON3K_VST3
```
See GitHub Actions for unsigned/ad-hoc signed development artifacts if the build succeeds. Install the macOS bundle in ~/Library/Audio/Plug-Ins/VST3 or the Windows bundle in C:\Program Files\Common Files\VST3. Scan in Ableton, set 48 kHz and select a local capture. No commercial captures bundled.

The plugin combines MIT project source with JUCE 8 (AGPLv3 or commercial terms), NAM Core and DaisySP including LGPL-2.1 components. The existing project MIT notice is unchanged; combined binaries require compliance with all applicable dependency terms, including corresponding source and relinking rights. This branch is experimental; do not redistribute until licensing is reviewed. Source and build instructions are in this branch, and dependency revisions are pinned in CMake and the workflow.
