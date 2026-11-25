# Experimental Debian packages

This branch targets Debian 13 / Raspberry Pi OS Trixie 64-bit only. No existing source installation is modified or migrated automatically. Install on a spare system first.

Build on the target architecture with git, build-essential, cmake, libasound2-dev, python3, dpkg-dev and ca-certificates installed:

    bash packaging/build-deb.sh 0.1.0~preview1

On arm64 optionally pass cortex-a72 (Pi 4) or cortex-a76 (Pi 5) as the second argument. Portable arm64 is the safest default. All variants share one package name; install only the appropriate variant.

    sudo apt install ./dist/<package>.deb

The service listens on localhost:8080 without authentication; use SSH forwarding from another computer:

    ssh -L 8080:127.0.0.1:8080 user@raspberrypi

Open http://localhost:8080 and configure PCM, channels and buffer in Audio settings. No audio starts automatically until enabled in /etc/default/rpi-ton3k. Pisound drivers must already be installed; select hw:pisound and configure the buffer and ADC reference explicitly. No hotspot, poweroff privileges, cloud integration or physical button is enabled by default.

Data lives in /var/lib/rpi-ton3k and survives upgrades, removal and purge. Existing source installation data remains separate; back up and migrate manually while both services are stopped. Never run both services on the same device. Remove with sudo apt remove rpi-ton3k. To resume the source installation, re-enable its original service.

This is packaging scaffolding, not a validated release. CI tests digital processing, not physical ALSA hardware or real-time performance. Do not install over the production setup until installation and upgrade tests pass.
