# DaisySP native effects

Unmodified upstream files: DaisySP MIT commit a0494a3adb67f549e18dfd71a35fa656f65b38b6; DaisySP-LGPL commit c89d380c62620d6fee9105c5035e081c9b7ea843.
Sources: https://github.com/daisyaudio/DaisySP and https://github.com/daisyaudio/DaisySP-LGPL.
The upstream copyright notices and full licenses are in mit/LICENSE and lgpl/LICENSE.
The compressor (Electrosmith, GRAME) and ReverbSc (Electrosmith, Sean Costello, Istvan Varga, Paul Batchelor) are LGPL-2.1, not MIT. RPiT3K wrapper code remains under the project's license.

CMake builds librpit3k-daisysp.so separately. Users can replace the LGPL library with an ABI-compatible modified build; source is included. When distributing binaries, include the shared library, applicable license texts and corresponding library source (or compliant offer), and allow replacement and debugging of modified library versions. The normal build-tree executable uses CMake's build RPATH. Do not copy the executable alone to another directory for distribution.

The original 0/1/2 preset values now select Dark/Bright/Neutral damping of ReverbSc, not spring/plate/room models. Decay is an approximate feedback mapping. NAM, gate, EQ, IR, metronome and ALSA are unchanged.
