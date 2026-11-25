#!/usr/bin/env bash
set -euo pipefail
# Optional poweroff capability. Run as the service's normal user.
if [[ $EUID == 0 ]]; then echo "Run as the normal service user, not root"; exit 1; fi
service=rpit3k-general.service
user="$(id -un)"
[[ "$user" =~ ^[a-zA-Z_][a-zA-Z0-9_-]*$ ]] || { echo "Unsupported username"; exit 1; }
[[ "$(systemctl show -p User --value "$service")" == "$user" ]] || { echo "Service user mismatch or missing service"; exit 1; }
test -x /usr/bin/sudo
test -x /usr/bin/systemctl
if [[ "${1:-}" == "--disable" ]]; then
 sudo rm -f /etc/sudoers.d/rpit3k-general-poweroff "/etc/systemd/system/$service.d/90-poweroff.conf"
 sudo systemctl daemon-reload
 sudo systemctl restart "$service"
 exit 0
fi
[[ $# == 0 ]] || { echo "Usage: bash rpi/install-poweroff.sh [--disable]"; exit 1; }
echo "WARNING: on unauthenticated LAN installations, anyone with API access can shut down the host."
read -rp 'Enable power off on this trusted installation? [y/N] ' answer
[[ "$answer" == y || "$answer" == Y ]] || exit 1
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
printf '%s ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff\n' "$user" > "$tmp"
sudo /usr/sbin/visudo -cf "$tmp"
sudo install -m 0440 -o root -g root "$tmp" /etc/sudoers.d/rpit3k-general-poweroff
sudo install -d -m 755 "/etc/systemd/system/$service.d"
printf '[Service]\nEnvironment=RPIT3K_ENABLE_POWEROFF=1\n' | sudo tee "/etc/systemd/system/$service.d/90-poweroff.conf" >/dev/null
sudo systemctl daemon-reload
sudo systemctl restart "$service"
echo "Power button enabled. No shutdown has been requested."
