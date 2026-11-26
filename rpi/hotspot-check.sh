#!/bin/bash
set -euo pipefail
iface="${1:-wlan0}"
[[ ! -e /run/rpit3k-hotspot-manual-off ]] || exit 0
# Leave a working Ethernet or Wi-Fi connection alone, including an active AP.
if nmcli -t -f TYPE,STATE device status | grep -Eq '^(wifi|ethernet):connected$'; then exit 0; fi
# Never interrupt ongoing connection attempts.
if nmcli -t -f DEVICE,STATE device status | grep -E "^$iface:connecting" >/dev/null; then exit 0; fi
nmcli connection up RPiT3K-fallback ifname "$iface"
