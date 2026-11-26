#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
systemctl cat pisound-btn.service >/dev/null
test -f /etc/pisound.conf
test -r /usr/local/pisound/scripts/common/common.sh
test -x /usr/local/pisound/scripts/pisound-btn/shutdown.sh
sudo cp -an /etc/pisound.conf /etc/pisound.conf.rpit3k-backup
sudo cp -a /etc/pisound.conf "/etc/pisound.conf.rpit3k-before-autonomous-$(date +%Y%m%d-%H%M%S)"
sudo install -m 755 "$root/rpi/pisound-button.sh" /usr/local/bin/rpit3k-button
for action in stomp next identify audio hotspot shutdown; do sudo ln -sfn rpit3k-button "/usr/local/bin/rpit3k-button-$action"; done
# Update an existing fallback helper too, without changing its connection/password.
if [[ -f /usr/local/bin/rpit3k-hotspot-check ]]; then sudo install -m 755 "$root/rpi/hotspot-check.sh" /usr/local/bin/rpit3k-hotspot-check; fi
sudo sed -i -E '/^[[:space:]]*(CLICK_1|CLICK_2|CLICK_3|HOLD_1S|HOLD_3S|HOLD_5S)[[:space:]]/d' /etc/pisound.conf
printf '\n' | sudo tee -a /etc/pisound.conf >/dev/null
sudo tee -a /etc/pisound.conf < "$root/rpi/pisound-button.conf" >/dev/null
sudo systemctl restart pisound-btn.service
echo "Pisound autonomous controls installed."
