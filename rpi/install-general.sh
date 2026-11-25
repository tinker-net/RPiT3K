#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID == 0 ]]; then echo "Run as a normal sudo-enabled user"; exit 1; fi
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
[[ "$(uname -s)" == Linux && "$(getconf LONG_BIT)" == 64 ]] || { echo "64-bit Linux required"; exit 1; }
case "$(uname -m)" in aarch64|x86_64) ;; *) echo "Unsupported architecture"; exit 1;; esac
command -v apt-get >/dev/null || { echo "Debian/Ubuntu/Raspberry Pi OS required for this installer"; exit 1; }
command -v systemctl >/dev/null
device=default
input_channel=1
input_channels=2
output_channels=2
output_left=1
output_right=2
buffer=256
periods=3
jobs=2
bind=127.0.0.1
cloud=--disable-cloud
while (($#)); do
 case "$1" in
  --device) device="${2:?missing PCM}"; shift;;
  --input-channel) input_channel="${2:?missing channel}"; shift;;
  --input-channels) input_channels="${2:?missing count}"; shift;;
  --output-channels) output_channels="${2:?missing count}"; shift;;
  --output-left) output_left="${2:?missing channel}"; shift;;
  --output-right) output_right="${2:?missing channel}"; shift;;
  --buffer) buffer="${2:?missing buffer}"; shift;;
  --periods) periods="${2:?missing periods}"; shift;;
  --jobs) jobs="${2:?missing jobs}"; shift;;
  --lan) bind=0.0.0.0;;
  --cloud) cloud=;;
  *) echo "Unknown option: $1"; exit 1;;
 esac
 shift
done
[[ "$root" =~ ^/[a-zA-Z0-9_./-]+$ && "$HOME" =~ ^/[a-zA-Z0-9_./-]+$ ]] || { echo "Unsupported checkout/home path"; exit 1; }
[[ "$device" =~ ^[a-zA-Z0-9_.,:=+-]+$ && "$jobs" =~ ^[1-9][0-9]*$ && "$buffer" =~ ^(64|128|256|512)$ && "$periods" =~ ^[234]$ ]] || { echo "Invalid settings"; exit 1; }
for n in "$input_channel" "$input_channels" "$output_channels" "$output_left" "$output_right"; do
 [[ "$n" =~ ^([1-9]|[1-5][0-9]|6[0-4])$ ]] || { echo "Invalid channel"; exit 1; }
done
((input_channel<=input_channels && output_left<=output_channels && output_right<=output_channels)) || { echo "Invalid routing"; exit 1; }
for service in rpit3k.service rpit3k-linux.service rpit3k-general.service; do
 if systemctl is-active --quiet "$service"; then echo "Stop $service before proceeding"; exit 1; fi
done
sudo apt-get update
sudo apt-get install -y git build-essential cmake libasound2-dev alsa-utils python3 curl ca-certificates
pin=d3189ed482ded880c128bf312941266c4fa5ceec
if [[ ! -e NeuralAmpModelerCore ]]; then git clone https://github.com/sdatkinson/NeuralAmpModelerCore.git; fi
if [[ "$(git -C NeuralAmpModelerCore rev-parse HEAD)" != "$pin" ]]; then
 [[ -z "$(git -C NeuralAmpModelerCore status --porcelain)" ]] || { echo "NAM Core has local changes"; exit 1; }
 git -C NeuralAmpModelerCore fetch origin "$pin"
 git -C NeuralAmpModelerCore checkout --detach "$pin"
fi
git -C NeuralAmpModelerCore submodule update --init --recursive
cpu=""
if [[ -r /proc/device-tree/model ]]; then
 model="$(tr -d '\0' </proc/device-tree/model)"
 case "$model" in *"Raspberry Pi 5"*|*"Compute Module 5"*) cpu=cortex-a76;; *"Raspberry Pi 4"*|*"Compute Module 4"*|*"Raspberry Pi 400"*) cpu=cortex-a72;; esac
fi
cmake -S rpi -B build-rpi -DCMAKE_BUILD_TYPE=Release -DRPIT3K_CPU="$cpu"
cmake --build build-rpi -j"$jobs"
ctest --test-dir build-rpi --output-on-failure
./build-rpi/rpit3k --bypass --verify
data="$HOME/.local/share/rpit3k-general"
install -d -m 700 "$data"
python3 - "$data/settings.json" "$device" "$buffer" "$periods" "$input_channel" "$input_channels" "$output_channels" "$output_left" "$output_right" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
if not p.exists():
    keys=("buffer","periods","input_channel","input_channels","output_channels","output_left","output_right")
    p.write_text(json.dumps(dict(device=sys.argv[2],last="1",reference_dbu=None,**dict(zip(keys,map(int,sys.argv[3:]))))))
PY
user="$(id -un)"
if [[ "$bind" == 0.0.0.0 ]]; then echo "WARNING: unauthenticated HTTP on trusted isolated LAN only"; fi
printf '[Unit]\nDescription=RPiT3K General native ALSA guitar processor\nAfter=sound.target\n\n[Service]\nType=simple\nUser=%s\nSupplementaryGroups=audio\nWorkingDirectory=%s\nExecStart=/usr/bin/python3 %s/rpi/server.py --bind %s --no-auth --autostart %s --data %s\nLimitRTPRIO=60\nRestart=on-failure\nRestartSec=3\nUMask=0077\n\n[Install]\nWantedBy=multi-user.target\n' "$user" "$root" "$root" "$bind" "$cloud" "$data" | sudo tee /etc/systemd/system/rpit3k-general.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable rpit3k-general.service
sudo systemctl restart rpit3k-general.service
echo "Local UI: http://127.0.0.1:8080 (use Audio settings if the hardware is not configured)"
aplay -l || true
arecord -l || true
for attempt in $(seq 1 15); do
 if curl --noproxy '*' --silent --fail --max-time 2 http://127.0.0.1:8080/api/levels | python3 -c 'import json,sys;sys.exit(not json.load(sys.stdin).get("valid"))' 2>/dev/null; then echo "Live audio telemetry confirmed"; exit 0; fi
 sleep 1
done
echo "Controller installed, but audio not verified. Configure the correct PCM and channels in Audio settings." >&2
exit 1
