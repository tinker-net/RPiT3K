#!/usr/bin/env bash
set -euo pipefail
# Run on the target Raspberry Pi as a normal sudo-enabled user.
if [[ $EUID == 0 ]]; then echo "Run as a normal sudo-enabled user"; exit 1; fi
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
[[ "$(uname -m)" == aarch64 && "$(getconf LONG_BIT)" == 64 ]] || { echo "64-bit Raspberry Pi OS required"; exit 1; }
[[ -r /proc/device-tree/model ]] && grep -aq 'Raspberry Pi' /proc/device-tree/model || { echo "Raspberry Pi required"; exit 1; }
command -v apt-get >/dev/null
command -v systemctl >/dev/null
model="$(tr -d '\0' </proc/device-tree/model)"
cpu=""
buffer=128
periods=3
if [[ "$model" == *"Raspberry Pi 5"* || "$model" == *"Compute Module 5"* ]]; then cpu=cortex-a76; buffer=64
elif [[ "$model" == *"Raspberry Pi 4"* || "$model" == *"Compute Module 4"* || "$model" == *"Raspberry Pi 400"* ]]; then cpu=cortex-a72
else buffer=256
fi
blokas=no
args=()
jobs=2
while (($#)); do
 case "$1" in
  --install-blokas) blokas=yes ;;
  --lan|--button|--cloud) args+=("$1") ;;
  --buffer) buffer="${2:?missing buffer}"; shift ;;
  --periods) periods="${2:?missing periods}"; shift ;;
  --jobs) jobs="${2:?missing jobs}"; shift ;;
  *) echo "Unknown option: $1"; exit 1 ;;
 esac
 shift
done
[[ "$jobs" =~ ^[1-9][0-9]*$ && "$buffer" =~ ^(64|128|256|512)$ && "$periods" =~ ^[234]$ ]] || { echo "Invalid settings"; exit 1; }
sudo apt-get update
sudo apt-get install -y git build-essential cmake libasound2-dev alsa-utils python3 curl ca-certificates ffmpeg
if [[ "$blokas" == yes ]]; then
 tmp="$(mktemp)"
 trap 'rm -f "$tmp"' EXIT
 curl --fail --location --proto '=https' https://blokas.io/pisound/install.sh -o "$tmp"
 sh "$tmp"
 rm -f "$tmp"
 echo "Blokas installer completed. Reboot, then rerun this script WITHOUT --install-blokas."
 exit 0
fi
if ! aplay -l | grep -qi pisound || ! arecord -l | grep -qi pisound; then
 echo "Pisound not detected. Run with --install-blokas, reboot, and rerun."
 exit 1
fi
pin=d3189ed482ded880c128bf312941266c4fa5ceec
if [[ ! -e NeuralAmpModelerCore ]]; then git clone https://github.com/sdatkinson/NeuralAmpModelerCore.git; fi
if [[ "$(git -C NeuralAmpModelerCore rev-parse HEAD)" != "$pin" ]]; then
 if [[ -n "$(git -C NeuralAmpModelerCore status --porcelain)" ]]; then echo "NAM Core has local changes; refusing checkout"; exit 1; fi
 git -C NeuralAmpModelerCore fetch origin "$pin"
 git -C NeuralAmpModelerCore checkout --detach "$pin"
fi
git -C NeuralAmpModelerCore submodule update --init --recursive
# Avoid build contention with an existing live engine.
if systemctl is-active --quiet rpit3k.service; then
 echo "Stop rpit3k.service before updating, then rerun: sudo systemctl stop rpit3k"
 exit 1
fi
cmake -S rpi -B build-rpi -DCMAKE_BUILD_TYPE=Release -DRPIT3K_CPU="$cpu"
cmake --build build-rpi -j"$jobs"
ctest --test-dir build-rpi --output-on-failure
./build-rpi/rpit3k --bypass --verify
bash rpi/install-service.sh --buffer "$buffer" --periods "$periods" "${args[@]}"
