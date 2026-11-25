#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID == 0 ]]; then echo "Run as your normal audio user"; exit 1; fi
if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: bash rpi/install-service.sh ALSA_DEVICE [INPUT_CHANNEL]"
  echo "Example: bash rpi/install-service.sh plughw:CARD=USB,DEV=0 2"
  exit 1
fi
device="$1"
channel="${2:-1}"
[[ "$device" =~ ^[a-zA-Z0-9_.,:=+-]+$ && "$channel" =~ ^[12]$ ]] || { echo "Invalid device or channel"; exit 1; }
root="$(cd "$(dirname "$0")/.." && pwd)"
user="$(id -un)"
home="$HOME"
[[ "$root" =~ ^/[a-zA-Z0-9_./-]+$ && "$home" =~ ^/[a-zA-Z0-9_./-]+$ ]] || { echo "Unsupported path"; exit 1; }
test -x "$root/build-rpi/rpit3k"
getent group audio >/dev/null || { echo "Debian audio group missing"; exit 1; }
# Separate unit and data directory: never overwrite the Pi-specific service.
if systemctl is-active --quiet rpit3k.service; then
  echo "Stop rpit3k.service before running the generic service (shared audio/port)."
  exit 1
fi
printf '[Unit]\nDescription=RPiT3K generic Linux audio processor\nAfter=sound.target\n\n[Service]\nType=simple\nUser=%s\nSupplementaryGroups=audio\nWorkingDirectory=%s\nExecStart=/usr/bin/python3 %s/rpi/server.py --bind 127.0.0.1 --no-auth --autostart --device %s --input-channel %s --data %s/.local/share/rpit3k-linux\nLimitRTPRIO=60\nRestart=on-failure\nRestartSec=3\n\n[Install]\nWantedBy=multi-user.target\n' "$user" "$root" "$root" "$device" "$channel" "$home" | sudo tee /etc/systemd/system/rpit3k-linux.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable rpit3k-linux.service
sudo systemctl restart rpit3k-linux.service
sudo systemctl --no-pager status rpit3k-linux.service
