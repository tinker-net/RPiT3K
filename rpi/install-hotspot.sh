#!/usr/bin/env bash
set -euo pipefail
# Separate opt-in to avoid disturbing the user's current network.
command -v nmcli >/dev/null
systemctl is-active --quiet NetworkManager
iface="${1:-wlan0}"
pass="${2:-}"
[[ "$iface" =~ ^[a-zA-Z0-9_-]+$ ]] || exit 1
if [[ -z "$pass" ]]; then read -rsp 'Hotspot WPA2 password (8-63 characters): ' pass; echo; fi
[[ ${#pass} -ge 8 && ${#pass} -le 63 ]] || { echo "Invalid password"; exit 1; }
if ! sudo nmcli connection show RPiT3K-fallback >/dev/null 2>&1; then
 sudo nmcli connection add type wifi ifname "$iface" con-name RPiT3K-fallback ssid RPiT3K
fi
sudo nmcli connection modify RPiT3K-fallback connection.autoconnect no 802-11-wireless.mode ap 802-11-wireless-security.key-mgmt wpa-psk 802-11-wireless-security.psk "$pass" ipv4.method shared ipv4.addresses 10.42.0.1/24 ipv6.method disabled
root="$(cd "$(dirname "$0")/.." && pwd)"
sudo install -m 755 "$root/rpi/hotspot-check.sh" /usr/local/bin/rpit3k-hotspot-check
printf '[Unit]\nDescription=RPiT3K fallback Wi-Fi check\nAfter=NetworkManager.service\n\n[Service]\nType=oneshot\nExecStart=/usr/local/bin/rpit3k-hotspot-check %s\n' "$iface" | sudo tee /etc/systemd/system/rpit3k-hotspot.service >/dev/null
printf '[Unit]\nDescription=Check for missing network on RPiT3K\n\n[Timer]\nOnBootSec=60s\nOnUnitActiveSec=30s\n\n[Install]\nWantedBy=timers.target\n' | sudo tee /etc/systemd/system/rpit3k-hotspot.timer >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now rpit3k-hotspot.timer
echo "Fallback hotspot RPiT3K: http://10.42.0.1"
