#!/usr/bin/env bash
set -euo pipefail
# Install from a normal sudo-enabled user. Existing service configuration is preserved
# unless explicitly reinstalled. Public LAN mode is an explicit opt-in.
if [[ $EUID == 0 ]]; then echo "Run as your normal user, not root"; exit 1; fi
root="$(cd "$(dirname "$0")/.." && pwd)"
user="$(id -un)"
home="$HOME"
bind=127.0.0.1
button=no
buffer=64
periods=3
while (($#)); do
 case "$1" in
  --lan) bind=0.0.0.0 ;;
  --button) button=yes ;;
  --buffer) buffer="${2:?missing buffer}"; shift ;;
  --periods) periods="${2:?missing periods}"; shift ;;
  *) echo "Unknown option: $1"; exit 1 ;;
 esac
 shift
done
[[ "$root" =~ ^/[a-zA-Z0-9_./-]+$ && "$home" =~ ^/[a-zA-Z0-9_./-]+$ && "$user" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo "Unsupported path or user"; exit 1; }
[[ "$buffer" =~ ^(64|128|256|512)$ && "$periods" =~ ^[234]$ ]] || { echo "Invalid ALSA settings"; exit 1; }
test -x "$root/build-rpi/rpit3k"
getent group audio >/dev/null
if systemctl is-active --quiet rpit3k-linux.service; then echo "Stop rpit3k-linux.service first"; exit 1; fi
if ! aplay -l | grep -qi 'pisound' || ! arecord -l | grep -qi 'pisound'; then
 echo "Pisound not detected in both ALSA directions. Install Blokas software and reboot first."
 exit 1
fi
sudo install -d -m 755 /etc/rpit3k
install -d -m 700 "$home/.local/share/rpit3k"
# Never overwrite existing presets or settings.
if [[ ! -e "$home/.local/share/rpit3k/settings.json" ]]; then
 (umask 077; printf '{"buffer":%s,"periods":%s,"last":"1"}\n' "$buffer" "$periods" > "$home/.local/share/rpit3k/settings.json")
fi
if [[ "$bind" == 0.0.0.0 ]]; then
 echo "WARNING: unauthenticated HTTP on the local network. Use only on a trusted isolated LAN."
fi
printf '[Unit]\nDescription=RPiT3K native pedal\nAfter=sound.target\n\n[Service]\nType=simple\nUser=%s\nSupplementaryGroups=audio\nWorkingDirectory=%s\nExecStart=/usr/bin/python3 %s/rpi/server.py --device hw:CARD=pisound,DEV=0 --bind %s --no-auth --autostart --data %s/.local/share/rpit3k\nLimitRTPRIO=60\nRestart=on-failure\nRestartSec=3\nUMask=0077\n\n[Install]\nWantedBy=multi-user.target\n' "$user" "$root" "$root" "$bind" "$home" | sudo tee /etc/systemd/system/rpit3k.service >/dev/null
sudo install -m 755 "$root/rpi/next-preset.sh" /usr/local/bin/rpit3k-next
if [[ "$button" == yes ]]; then
 if systemctl cat pisound-btn.service >/dev/null 2>&1 && [[ -f /etc/pisound.conf ]]; then
  sudo cp -an /etc/pisound.conf /etc/pisound.conf.rpit3k-backup
  sudo sed -i -E '/^[[:space:]]*CLICK_1[[:space:]]/d' /etc/pisound.conf
  printf '\nCLICK_1 /usr/local/bin/rpit3k-next\n' | sudo tee -a /etc/pisound.conf >/dev/null
  sudo systemctl restart pisound-btn.service
 else
  echo "Pisound button service/config not found; button not configured."
 fi
fi
sudo systemctl daemon-reload
sudo systemctl enable rpit3k.service
sudo systemctl restart rpit3k.service
sudo systemctl --no-pager status rpit3k.service
echo "Local UI: http://127.0.0.1:8080"
