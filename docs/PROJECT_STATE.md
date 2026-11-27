# PiSound validation — 2026-11-26

Tested source: 9204edb435b88868034b2e00cebda2165c1b4550 (development). Raspberry Pi 5 4 GiB, PiSound, Trixie, 48 kHz, 64 frames × 3 periods.

## Results
[CI run 45903870265](https://github.com/tinker-net/RPiT3K/actions/runs/45903870265): ARM Cortex-A76 and x86-64 builds, 10/10 CTest each, bypass VERIFY PASS, Python button/policy tests and syntax checks. Nine consecutive development revisions passed after the initial compile fix. Local Pi: 10/10 CTest (3.83 s), VERIFY PASS, 3 Python tests passed, clean checkout. System snapshot: 290 MiB RAM used, 3.7 GiB available, swap 0, disk 11%, 58.2°C, throttled 0x0.

| Measurement | Reference | FFmpeg present |
| --- | ---: | ---: |
| DSP mean approximate (µs) | 320 | 323 |
| Maximum reported (µs) | 524.038 | 474.798 |
| Deadline (µs) | 1333.33 | 1333.33 |
| Late blocks / xruns | 0 / 0 | 0 / 0 |
| Window | ~100 s | ~100 s |

One NAM present, one IR, IR2 absent; second NAM state not reported. Input practically silent. FFmpeg present at second process snapshot, not proof of continuous playback or exact speed/pitch settings throughout window. DSP timing excludes some mixer/ALSA work. Process snapshot: engine CPU 3 FIFO 60 RSS 9136 KiB, Python CPU 1 RSS 40608 KiB, FFmpeg CPU 2 nice +10 RSS 56384 KiB. Lifetime CPU percentages 20.4, 16.3, 0.8 respectively. Residency not proof of exclusive cores. No observed regression in these windows.

Pending: real guitar/full dual NAM/IR/effects stress, transport timing and teardown, sustained load, backup restore, semantic library accuracy, merged main CI, package and DAW integration. Published DEBs and native artifacts remain older snapshots.

## Recovery
[fallback/pre-practice](https://github.com/tinker-net/RPiT3K/tree/fallback/pre-practice) points to db73ecaabb5098216929c5b0722eb4c0130b9d1c, the last source before Practice Mode. rpi-ui remains unchanged. From clean source checkout:
```sh
cd ~/RPiT3K
git fetch origin
sudo systemctl stop rpit3k.service
git switch --detach origin/fallback/pre-practice
cmake -S rpi -B build-rpi -DCMAKE_BUILD_TYPE=Release -DRPIT3K_CPU=cortex-a76 && cmake --build build-rpi -j2 && ctest --test-dir build-rpi --output-on-failure && sudo systemctl start rpit3k.service
```
No personal files deleted; audio starts OFF. Hard refresh browser. Return with git switch main, rebuild and restart. FFmpeg can remain installed.

## Experimental practice reader — 2026-11-28
Branch `experimental/guitar-pro`, based on stable main 735caad. Local alphaTab 1.8.4, GP3–8 reader, track/notation/zoom; optional score below existing waveform. Browser-only MIDI synthesis with local SONiVOX, separate transport, loop selection, per-track mute/solo/volume and tempo. Waveform Device/Browser selector; Device path unchanged, Browser uses media streaming, speed preserving pitch, independent semitone adjustment unavailable in Browser, approximate loops and browser-dependent codecs. No automatic synchronization or transcription. No changes to ALSA/DSP, stable main, or published packages. Score files are browser-local, not persistent. Pending: npm asset installation on Pi, actual GP8 rendering, MIDI readiness/mixer/selection, HTTP browser audio fallback, route switches, pause/seek/loop/close, mobile sizing and regression testing. Do not merge until tested.

Metronome output is independently selectable: Device (default, native click, Audio ON required) or Browser (Web Audio clock scheduling, independent of guitar engine). Switching stops the current click before selecting the other route; press Start again. Browser settings are local to the page. Browser timing, route switching and audio-off operation require acceptance testing; background tab throttling may affect click continuity. No DSP changes.
