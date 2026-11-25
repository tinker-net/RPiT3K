#!/usr/bin/env bash
set -euo pipefail
# Run as the normal Pi audio user, not root.
if [[ $EUID == 0 ]]; then echo "Run as your normal user"; exit 1; fi
root="$(cd "$(dirname "$0")/.." && pwd)"
user="$(id -un)"
home="$HOME"
[[ "$root" =~ ^/[a-zA-Z0-9_./-]+$ && "$home" =~ ^/[a-zA-Z0-9_./-]+$ ]] || { echo "Unsupported path"; exit 1; }
test -x "$root/build-rpi/rpit3k"
sudo install -d -m 755 /etc/rpit3k
printf '[Unit]\nDescription=RPiT3K native pedal\nAfter=sound.target\n\n[Service]\nType=simple\nUser=%s\nSupplementaryGroups=audio\nWorkingDirectory=%s\nExecStart=/usr/bin/python3 %s/rpi/server.py --bind 0.0.0.0 --no-auth --autostart --data %s/.local/share/rpit3k\nLimitRTPRIO=60\nRestart=on-failure\nRestartSec=3\n\n[Install]\nWantedBy=multi-user.target\n' "$user" "$root" "$root" "$home" | sudo tee /etc/systemd/system/rpit3k.service >/dev/null
sudo install -m 755 "$root/rpi/next-preset.sh" /usr/local/bin/rpit3k-next
if systemctl cat pisound-btn.service >/dev/null 2>&1 && [[ -f /etc/pisound.conf ]]; then
  sudo cp -an /etc/pisound.conf /etc/pisound.conf.rpit3k-backup
  sudo sed -i -E '/^[[:space:]]*CLICK_1[[:space:]]/d' /etc/pisound.conf
  printf '\nCLICK_1 /usr/local/bin/rpit3k-next\n' | sudo tee -a /etc/pisound.conf >/dev/null
  sudo systemctl restart pisound-btn.service
else
  echo "Pisound button service/config not found; physical button not configured."
fi
sudo systemctl daemon-reload
sudo systemctl enable --now rpit3k.service
sudo systemctl restart rpit3k.service
sudo systemctl --no-pager status rpit3k.service
